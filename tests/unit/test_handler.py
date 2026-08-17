"""Unit tests for the Lambda handler and API routing."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from nutritrack.domain.models import (
    ActivityLevel,
    DailyGoal,
    DailySummary,
    FoodEntry,
    GoalStatus,
    Sex,
    UserProfile,
    WeightRecord,
)
from nutritrack.handler import (
    CORS_HEADERS,
    _make_response,
    _serialize,
    handler,
)
from nutritrack.use_cases.exceptions import (
    AIServiceUnavailableError,
    FoodNotRecognizedError,
    InvalidImageError,
)
from nutritrack.use_cases.results import (
    AddEntryResult,
    OnboardingResult,
    WeightUpdateResult,
)


# --- Helper to build API Gateway v2 events ---


def _build_event(method: str, path: str, body: dict | None = None, query_params: dict | None = None) -> dict:
    """Build an API Gateway HTTP API v2 event."""
    event = {
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            }
        },
        "queryStringParameters": query_params,
        "body": json.dumps(body) if body else None,
    }
    return event


# --- Fixtures ---


@pytest.fixture
def sample_profile():
    return UserProfile(
        weight_kg=75.0,
        height_cm=175.0,
        age=30,
        sex=Sex.MALE,
        activity_level=ActivityLevel.MODERATE,
        daily_calorie_goal=2000,
        tdee=2400,
    )


@pytest.fixture
def sample_entry():
    return FoodEntry(
        entry_id="abc123",
        food_name="Grilled chicken salad",
        calories=450,
        confidence=0.87,
        timestamp="2024-01-15T12:30:00+00:00",
        date="2024-01-15",
    )


# --- Test CORS headers ---


class TestCORSHeaders:
    def test_cors_headers_on_successful_response(self, sample_profile):
        """All responses include CORS headers."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = sample_profile
            mock_repo_factory.return_value = mock_repo

            event = _build_event("GET", "/profile")
            response = handler(event, None)

            assert response["headers"]["Access-Control-Allow-Origin"] == "*"
            assert response["headers"]["Access-Control-Allow-Headers"] == "Content-Type, Authorization"
            assert response["headers"]["Access-Control-Allow-Methods"] == "GET, POST, PUT, DELETE, OPTIONS"

    def test_cors_headers_on_error_response(self):
        """Error responses also include CORS headers."""
        event = _build_event("GET", "/nonexistent")
        response = handler(event, None)

        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert response["headers"]["Access-Control-Allow-Headers"] == "Content-Type, Authorization"
        assert response["headers"]["Access-Control-Allow-Methods"] == "GET, POST, PUT, DELETE, OPTIONS"

    def test_options_preflight(self):
        """OPTIONS requests return 200 with CORS headers."""
        event = _build_event("OPTIONS", "/entries")
        response = handler(event, None)

        assert response["statusCode"] == 200
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"


# --- Test routing ---


class TestRouting:
    def test_unknown_route_returns_404(self):
        """Unregistered routes return 404."""
        event = _build_event("PATCH", "/entries")
        response = handler(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Not found" in body["error"]

    def test_get_profile_not_found(self):
        """GET /profile returns 404 when no profile exists."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = None
            mock_repo_factory.return_value = mock_repo

            event = _build_event("GET", "/profile")
            response = handler(event, None)

            assert response["statusCode"] == 404

    def test_get_profile_success(self, sample_profile):
        """GET /profile returns 200 with profile data."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = sample_profile
            mock_repo_factory.return_value = mock_repo

            event = _build_event("GET", "/profile")
            response = handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["weight_kg"] == 75.0
            assert body["sex"] == "male"
            assert body["activity_level"] == "moderate"

    def test_post_profile_conflict(self, sample_profile):
        """POST /profile returns 409 if profile already exists."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = sample_profile
            mock_repo_factory.return_value = mock_repo

            event = _build_event("POST", "/profile", body={
                "weight_kg": 75,
                "height_cm": 175,
                "age": 30,
                "sex": "male",
                "activity_level": "moderate",
            })
            response = handler(event, None)

            assert response["statusCode"] == 409

    def test_post_profile_success(self):
        """POST /profile creates profile and returns 201."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = None
            mock_repo.save_profile.return_value = None
            mock_repo.save_weight_record.return_value = None
            mock_repo_factory.return_value = mock_repo

            event = _build_event("POST", "/profile", body={
                "weight_kg": 75,
                "height_cm": 175,
                "age": 30,
                "sex": "male",
                "activity_level": "moderate",
            })
            response = handler(event, None)

            assert response["statusCode"] == 201
            body = json.loads(response["body"])
            assert "tdee" in body
            assert "suggested_goal" in body

    def test_put_profile_goal_success(self, sample_profile):
        """PUT /profile/goal updates the goal and returns 200."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = sample_profile
            mock_repo.save_profile.return_value = None
            mock_repo_factory.return_value = mock_repo

            event = _build_event("PUT", "/profile/goal", body={"daily_calorie_goal": 1800})
            response = handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["daily_calorie_goal"] == 1800

    def test_get_weight_history(self):
        """GET /weight/history returns weight records."""
        records = [
            WeightRecord(date="2024-01-15", weight_kg=75.0),
            WeightRecord(date="2024-01-10", weight_kg=76.0),
        ]
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_weight_history.return_value = records
            mock_repo_factory.return_value = mock_repo

            event = _build_event("GET", "/weight/history", query_params={"limit": "10"})
            response = handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert len(body["records"]) == 2
            assert body["records"][0]["weight_kg"] == 75.0


# --- Test exception mapping ---


class TestExceptionMapping:
    def test_invalid_image_empty_returns_400(self):
        """InvalidImageError (empty) maps to 400."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory:
            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = UserProfile(
                weight_kg=75, height_cm=175, age=30, sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE, daily_calorie_goal=2000, tdee=2400,
            )
            mock_repo_factory.return_value = mock_repo

            # Empty image field
            event = _build_event("POST", "/entries", body={"image": ""})
            response = handler(event, None)

            assert response["statusCode"] == 400

    def test_invalid_image_too_large_returns_413(self):
        """InvalidImageError (too large) maps to 413."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory, \
             patch("nutritrack.handler._get_image_analyzer") as mock_analyzer_factory, \
             patch("nutritrack.handler._get_entry_repository") as mock_entry_factory:

            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = UserProfile(
                weight_kg=75, height_cm=175, age=30, sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE, daily_calorie_goal=2000, tdee=2400,
            )
            mock_repo_factory.return_value = mock_repo

            mock_analyzer = AsyncMock()
            mock_analyzer.analyze_food_image.side_effect = InvalidImageError("Image exceeds 20MB limit")
            mock_analyzer_factory.return_value = mock_analyzer

            mock_entry_repo = AsyncMock()
            mock_entry_factory.return_value = mock_entry_repo

            # Use a minimal base64 string (the actual size check happens in add_food_entry use case)
            import base64
            # We simulate the error being raised from add_food_entry
            with patch("nutritrack.handler.add_food_entry", side_effect=InvalidImageError("Image exceeds 20MB limit")):
                event = _build_event("POST", "/entries", body={"image": base64.b64encode(b"x").decode()})
                response = handler(event, None)

                assert response["statusCode"] == 413

    def test_food_not_recognized_returns_400(self):
        """FoodNotRecognizedError maps to 400 with code."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory, \
             patch("nutritrack.handler._get_image_analyzer") as mock_analyzer_factory, \
             patch("nutritrack.handler._get_entry_repository") as mock_entry_factory, \
             patch("nutritrack.handler.add_food_entry", side_effect=FoodNotRecognizedError("Not food")):

            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = UserProfile(
                weight_kg=75, height_cm=175, age=30, sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE, daily_calorie_goal=2000, tdee=2400,
            )
            mock_repo_factory.return_value = mock_repo
            mock_analyzer_factory.return_value = AsyncMock()
            mock_entry_factory.return_value = AsyncMock()

            import base64
            event = _build_event("POST", "/entries", body={"image": base64.b64encode(b"img").decode()})
            response = handler(event, None)

            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert body["code"] == "food_not_recognized"

    def test_ai_unavailable_returns_503(self):
        """AIServiceUnavailableError maps to 503 with retry_after."""
        with patch("nutritrack.handler._get_profile_repository") as mock_repo_factory, \
             patch("nutritrack.handler._get_image_analyzer") as mock_analyzer_factory, \
             patch("nutritrack.handler._get_entry_repository") as mock_entry_factory, \
             patch("nutritrack.handler.add_food_entry", side_effect=AIServiceUnavailableError("API down")):

            mock_repo = AsyncMock()
            mock_repo.get_profile.return_value = UserProfile(
                weight_kg=75, height_cm=175, age=30, sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE, daily_calorie_goal=2000, tdee=2400,
            )
            mock_repo_factory.return_value = mock_repo
            mock_analyzer_factory.return_value = AsyncMock()
            mock_entry_factory.return_value = AsyncMock()

            import base64
            event = _build_event("POST", "/entries", body={"image": base64.b64encode(b"img").decode()})
            response = handler(event, None)

            assert response["statusCode"] == 503
            body = json.loads(response["body"])
            assert "retry_after" in body

    def test_value_error_returns_400(self):
        """ValueError from validation maps to 400."""
        event = _build_event("GET", "/summary", query_params={})
        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "date" in body["error"].lower()


# --- Test serialization ---


class TestSerialization:
    def test_serialize_enum(self):
        """Enums are serialized to their string values."""
        assert _serialize(GoalStatus.WITHIN_GOAL) == "within_goal"
        assert _serialize(Sex.MALE) == "male"

    def test_serialize_dataclass(self, sample_entry):
        """Dataclasses are serialized to dicts."""
        result = _serialize(sample_entry)
        assert isinstance(result, dict)
        assert result["food_name"] == "Grilled chicken salad"
        assert result["calories"] == 450

    def test_serialize_list(self, sample_entry):
        """Lists of dataclasses are serialized recursively."""
        result = _serialize([sample_entry, sample_entry])
        assert isinstance(result, list)
        assert len(result) == 2

    def test_make_response_format(self):
        """_make_response returns proper Lambda format."""
        resp = _make_response(200, {"key": "value"})
        assert resp["statusCode"] == 200
        assert resp["headers"] == CORS_HEADERS
        assert json.loads(resp["body"]) == {"key": "value"}
