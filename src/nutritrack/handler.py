"""AWS Lambda handler with API Gateway HTTP API v2 routing.

Single entry point for all API routes. Parses the event, routes by
HTTP method + path, executes the appropriate use case, and returns
a properly formatted Lambda response with CORS headers.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from nutritrack.domain.models import (
    ActivityLevel,
    DailyGoal,
    DailySummary,
    FoodEntry,
    Sex,
    UserProfile,
    WeightRecord,
)
from nutritrack.infrastructure.dynamodb import (
    DynamoDBEntryRepository,
    DynamoDBUserProfileRepository,
)
from nutritrack.infrastructure.bedrock_analyzer import BedrockImageAnalyzer
from nutritrack.use_cases.add_food_entry import add_food_entry
from nutritrack.use_cases.complete_onboarding import complete_onboarding
from nutritrack.use_cases.exceptions import (
    AIServiceUnavailableError,
    FoodNotRecognizedError,
    InvalidImageError,
)
from nutritrack.use_cases.get_daily_summary import get_daily_summary
from nutritrack.use_cases.update_weight import update_weight

# --- Environment variable initialization ---

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "nutritrack-entries")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
AWS_REGION = os.environ.get("APP_AWS_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# --- CORS headers applied to all responses ---

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Content-Type": "application/json",
}


# --- Serialization helpers ---


def _serialize(obj: Any) -> Any:
    """Recursively serialize dataclasses, enums, and lists to JSON-safe dicts."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {key: _serialize(value) for key, value in asdict(obj).items()}
    return obj


def _make_response(status_code: int, body: Any) -> dict:
    """Create a Lambda proxy response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


# --- Dependency initialization ---


def _get_entry_repository() -> DynamoDBEntryRepository:
    return DynamoDBEntryRepository(table_name=DYNAMODB_TABLE)


def _get_profile_repository() -> DynamoDBUserProfileRepository:
    return DynamoDBUserProfileRepository(table_name=DYNAMODB_TABLE)


def _get_image_analyzer() -> BedrockImageAnalyzer:
    return BedrockImageAnalyzer(region=AWS_REGION, model_id=BEDROCK_MODEL_ID)


# --- Route handlers ---


async def _handle_post_entries(body: dict) -> dict:
    """POST /entries — Upload food image, get AI analysis + calorie entry."""
    image_base64 = body.get("image_data") or body.get("image", "")
    if not image_base64:
        raise InvalidImageError("Image data must not be empty")

    image_data = base64.b64decode(image_base64)

    # Get the user's profile for calorie goal
    profile_repo = _get_profile_repository()
    profile = await profile_repo.get_profile()
    if profile is None:
        return _make_response(404, {"error": "Profile not found. Complete onboarding first."})

    daily_goal = DailyGoal(target_calories=profile.daily_calorie_goal)
    image_analyzer = _get_image_analyzer()
    entry_repository = _get_entry_repository()

    # Use client's local date if provided, otherwise UTC
    local_date = body.get("date", "")

    result = await add_food_entry(
        image_data=image_data,
        image_analyzer=image_analyzer,
        entry_repository=entry_repository,
        daily_goal=daily_goal,
        local_date=local_date,
    )

    return _make_response(201, _serialize(result))


async def _handle_get_summary(query_params: dict) -> dict:
    """GET /summary?date=YYYY-MM-DD — Get daily summary."""
    target_date = query_params.get("date", "")
    if not target_date:
        raise ValueError("Query parameter 'date' is required")

    profile_repo = _get_profile_repository()
    profile = await profile_repo.get_profile()
    if profile is None:
        return _make_response(404, {"error": "Profile not found. Complete onboarding first."})

    daily_goal = DailyGoal(target_calories=profile.daily_calorie_goal)

    summary = await get_daily_summary(
        target_date=target_date,
        entry_repository=_get_entry_repository(),
        daily_goal=daily_goal,
    )

    return _make_response(200, _serialize(summary))


async def _handle_get_profile() -> dict:
    """GET /profile — Get user profile (404 if not onboarded)."""
    profile_repo = _get_profile_repository()
    profile = await profile_repo.get_profile()
    if profile is None:
        return _make_response(404, {"error": "Profile not found"})

    return _make_response(200, _serialize(profile))


async def _handle_post_profile(body: dict) -> dict:
    """POST /profile — Create profile during onboarding."""
    # Check if profile already exists
    profile_repo = _get_profile_repository()
    existing = await profile_repo.get_profile()
    if existing is not None:
        return _make_response(409, {"error": "Profile already exists"})

    # Parse and validate input
    try:
        weight_kg = float(body.get("weight_kg", 0))
        height_cm = float(body.get("height_cm", 0))
        age = int(body.get("age", 0))
        sex = Sex(body.get("sex", ""))
        activity_level = ActivityLevel(body.get("activity_level", ""))
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Invalid onboarding data: {exc}")

    result = await complete_onboarding(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        activity_level=activity_level,
        profile_repository=profile_repo,
    )

    return _make_response(201, _serialize(result))


async def _handle_put_profile_goal(body: dict) -> dict:
    """PUT /profile/goal — Update daily calorie goal."""
    profile_repo = _get_profile_repository()
    profile = await profile_repo.get_profile()
    if profile is None:
        return _make_response(404, {"error": "Profile not found"})

    new_goal = body.get("daily_calorie_goal")
    if new_goal is None:
        raise ValueError("Field 'daily_calorie_goal' is required")

    new_goal = int(new_goal)
    if not (500 <= new_goal <= 10000):
        raise ValueError("daily_calorie_goal must be between 500 and 10000")

    # Create updated profile with new goal
    updated_profile = UserProfile(
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        activity_level=profile.activity_level,
        daily_calorie_goal=new_goal,
        tdee=profile.tdee,
    )

    await profile_repo.save_profile(updated_profile)

    return _make_response(200, _serialize(updated_profile))


async def _handle_post_weight(body: dict) -> dict:
    """POST /weight — Record new weight, recalculate TDEE."""
    new_weight = body.get("weight_kg")
    if new_weight is None:
        raise ValueError("Field 'weight_kg' is required")

    new_weight_kg = float(new_weight)

    profile_repo = _get_profile_repository()
    result = await update_weight(
        new_weight_kg=new_weight_kg,
        profile_repository=profile_repo,
    )

    return _make_response(200, _serialize(result))


async def _handle_get_weight_history(query_params: dict) -> dict:
    """GET /weight/history?limit=30 — Get weight history for charts."""
    limit_str = query_params.get("limit", "30")
    try:
        limit = int(limit_str)
    except (ValueError, TypeError):
        limit = 30

    profile_repo = _get_profile_repository()
    history = await profile_repo.get_weight_history(limit=limit)

    return _make_response(200, {"records": _serialize(history)})


async def _handle_get_summary_week(query_params: dict) -> dict:
    """GET /summary/week?start=YYYY-MM-DD — Get 7-day summary for weekly chart."""
    start_date_str = query_params.get("start", "")
    if not start_date_str:
        raise ValueError("Query parameter 'start' is required")

    profile_repo = _get_profile_repository()
    profile = await profile_repo.get_profile()
    if profile is None:
        return _make_response(404, {"error": "Profile not found. Complete onboarding first."})

    daily_goal = DailyGoal(target_calories=profile.daily_calorie_goal)
    entry_repo = _get_entry_repository()

    # Fetch summaries for 7 days starting from start_date
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    summaries = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        summary = await get_daily_summary(
            target_date=day_str,
            entry_repository=entry_repo,
            daily_goal=daily_goal,
        )
        summaries.append(summary)

    return _make_response(200, {"summaries": _serialize(summaries)})


async def _handle_delete_entry(body: dict) -> dict:
    """DELETE /entries — Remove a food entry by date and entry_id."""
    entry_id = body.get("entry_id", "")
    date = body.get("date", "")
    if not entry_id or not date:
        raise ValueError("Fields 'entry_id' and 'date' are required")

    entry_repo = _get_entry_repository()
    await entry_repo.delete_entry(date=date, entry_id=entry_id)

    return _make_response(200, {"deleted": True, "entry_id": entry_id})


# --- Router ---

# Maps (method, path) to handler coroutines
_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/entries"): "_handle_post_entries",
    ("DELETE", "/entries"): "_handle_delete_entry",
    ("GET", "/summary"): "_handle_get_summary",
    ("GET", "/profile"): "_handle_get_profile",
    ("POST", "/profile"): "_handle_post_profile",
    ("PUT", "/profile/goal"): "_handle_put_profile_goal",
    ("POST", "/weight"): "_handle_post_weight",
    ("GET", "/weight/history"): "_handle_get_weight_history",
    ("GET", "/summary/week"): "_handle_get_summary_week",
}


async def _route_request(method: str, path: str, body: dict, query_params: dict) -> dict:
    """Route the request to the appropriate handler based on method + path."""
    route_key = (method, path)

    if route_key not in _ROUTES:
        return _make_response(404, {"error": f"Not found: {method} {path}"})

    handler_name = _ROUTES[route_key]
    handler_func = globals()[handler_name]

    # Determine which arguments the handler needs based on route
    if handler_name == "_handle_get_profile":
        return await handler_func()
    elif method == "GET":
        return await handler_func(query_params)
    else:
        return await handler_func(body)


# --- Lambda entry point ---


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda handler — single entry point for API Gateway HTTP API v2.

    Parses the event, routes to the correct handler, maps exceptions
    to HTTP status codes, and ensures CORS headers on all responses.
    """
    # Handle CORS preflight
    http_context = event.get("requestContext", {}).get("http", {})
    method = http_context.get("method", "").upper()
    path = http_context.get("path", "")

    if method == "OPTIONS":
        return _make_response(200, {})

    # Parse query parameters
    query_params = event.get("queryStringParameters") or {}

    # Parse request body
    body: dict = {}
    raw_body = event.get("body", "")
    if raw_body:
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, TypeError):
            body = {}

    # Route and handle exceptions
    try:
        response = asyncio.run(_route_request(method, path, body, query_params))
        return response
    except InvalidImageError as exc:
        error_msg = str(exc)
        if "20MB" in error_msg or "too large" in error_msg.lower():
            return _make_response(413, {"error": error_msg})
        return _make_response(400, {"error": error_msg})
    except FoodNotRecognizedError as exc:
        return _make_response(400, {"error": str(exc), "code": "food_not_recognized"})
    except ValueError as exc:
        return _make_response(400, {"error": str(exc)})
    except AIServiceUnavailableError as exc:
        return _make_response(503, {
            "error": str(exc),
            "retry_after": 30,
        })
    except Exception as exc:
        return _make_response(500, {"error": "Internal server error"})
