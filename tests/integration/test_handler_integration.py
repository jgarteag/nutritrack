"""Integration tests for the Lambda handler with moto-mocked DynamoDB.

These tests exercise the FULL code path: event → handler → use case → DynamoDB.
Only the Bedrock API is mocked. DynamoDB is simulated via moto so that the entire
repository layer runs against a real (in-memory) table.
"""

import base64
import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from nutritrack.use_cases.results import FoodAnalysisResult


# --- Constants ---

TABLE_NAME = "nutritrack-test-table"


# --- Helpers ---


def _build_event(
    method: str,
    path: str,
    body: dict | None = None,
    query_params: dict | None = None,
) -> dict:
    """Build an API Gateway HTTP API v2 event."""
    return {
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            }
        },
        "queryStringParameters": query_params,
        "body": json.dumps(body) if body else None,
    }


# --- Fixtures ---


@pytest.fixture(autouse=True)
def aws_env_and_table():
    """Set up environment variables and create DynamoDB table with moto.

    This fixture:
    1. Sets required env vars (DYNAMODB_TABLE, OPENAI_API_KEY, AWS creds)
    2. Creates the DynamoDB table in moto
    3. Re-imports the handler module so it picks up the new env vars
    """
    with mock_aws():
        # Set env vars before handler module reads them
        env_patch = patch.dict(os.environ, {
            "DYNAMODB_TABLE": TABLE_NAME,
            "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
            "AWS_REGION": "us-east-1",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
        })
        env_patch.start()

        # Create DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Reload handler to pick up new DYNAMODB_TABLE env var
        import importlib
        import nutritrack.handler as handler_module
        importlib.reload(handler_module)

        yield handler_module.handler

        env_patch.stop()


def _mock_bedrock_response(food_name: str, calories: int, confidence: float):
    """Create a mock Bedrock Converse API response."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": json.dumps({
                    "food_name": food_name,
                    "estimated_calories": calories,
                    "confidence": confidence,
                })}],
            }
        },
        "stopReason": "end_turn",
    }


# ===========================================================================
# FULL LAMBDA HANDLER INTEGRATION TESTS
# ===========================================================================


class TestProfileIntegration:
    """Test profile-related endpoints with real DynamoDB interactions."""

    def test_get_profile_returns_404_when_no_profile(self, aws_env_and_table):
        """GET /profile returns 404 when no profile exists."""
        handler = aws_env_and_table
        event = _build_event("GET", "/profile")
        response = handler(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "not found" in body["error"].lower()

    def test_post_profile_creates_profile(self, aws_env_and_table):
        """POST /profile creates a profile and returns 201 with TDEE."""
        handler = aws_env_and_table
        event = _build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        })
        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert "tdee" in body
        assert "suggested_goal" in body
        assert body["tdee"] > 0
        assert body["suggested_goal"] > 0

    def test_get_profile_after_creation(self, aws_env_and_table):
        """GET /profile returns 200 with profile data after creation."""
        handler = aws_env_and_table

        # Create profile first
        create_event = _build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        })
        handler(create_event, None)

        # Now retrieve it
        get_event = _build_event("GET", "/profile")
        response = handler(get_event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["weight_kg"] == 75.0
        assert body["height_cm"] == 175.0
        assert body["age"] == 30
        assert body["sex"] == "male"
        assert body["activity_level"] == "moderate"

    def test_post_profile_duplicate_returns_409(self, aws_env_and_table):
        """POST /profile returns 409 if profile already exists."""
        handler = aws_env_and_table
        profile_body = {
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        }

        # Create profile
        handler(_build_event("POST", "/profile", body=profile_body), None)

        # Try creating again
        response = handler(_build_event("POST", "/profile", body=profile_body), None)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert "already exists" in body["error"].lower()

    def test_put_profile_goal_updates_goal(self, aws_env_and_table):
        """PUT /profile/goal updates the calorie goal."""
        handler = aws_env_and_table

        # Create profile first
        handler(_build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        }), None)

        # Update goal
        response = handler(
            _build_event("PUT", "/profile/goal", body={"daily_calorie_goal": 1800}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["daily_calorie_goal"] == 1800

    def test_put_profile_goal_without_profile_returns_404(self, aws_env_and_table):
        """PUT /profile/goal returns 404 if no profile exists."""
        handler = aws_env_and_table
        response = handler(
            _build_event("PUT", "/profile/goal", body={"daily_calorie_goal": 1800}),
            None,
        )

        assert response["statusCode"] == 404


class TestWeightIntegration:
    """Test weight-related endpoints with real DynamoDB interactions."""

    def _create_profile(self, handler):
        """Helper: create a profile for weight tests."""
        handler(_build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        }), None)

    def test_post_weight_updates_profile(self, aws_env_and_table):
        """POST /weight updates weight, recalculates TDEE."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("POST", "/weight", body={"weight_kg": 73.0}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["new_tdee"] > 0
        assert body["suggested_goal"] > 0
        assert "weight_history" in body

    def test_post_weight_without_profile_returns_400(self, aws_env_and_table):
        """POST /weight returns 400 if no profile exists."""
        handler = aws_env_and_table
        response = handler(
            _build_event("POST", "/weight", body={"weight_kg": 73.0}),
            None,
        )

        # The use case raises ValueError("No profile exists...")
        assert response["statusCode"] == 400

    def test_get_weight_history(self, aws_env_and_table):
        """GET /weight/history returns weight records after updates."""
        handler = aws_env_and_table
        self._create_profile(handler)

        # Add another weight entry
        handler(_build_event("POST", "/weight", body={"weight_kg": 74.0}), None)

        response = handler(
            _build_event("GET", "/weight/history", query_params={"limit": "10"}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        # Should have at least 1 record (initial weight from onboarding + update may overlap on same day)
        assert len(body["records"]) >= 1


class TestEntriesIntegration:
    """Test food entry endpoints with real DynamoDB and mocked OpenAI."""

    def _create_profile(self, handler):
        """Helper: create a profile for entry tests."""
        handler(_build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        }), None)

    def test_post_entries_success(self, aws_env_and_table):
        """POST /entries analyzes an image and creates an entry."""
        handler = aws_env_and_table
        self._create_profile(handler)

        mock_response = _mock_bedrock_response("Grilled chicken", 450, 0.9)

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto3.client.return_value = mock_client

            image_b64 = base64.b64encode(b"fake-image-data").decode()
            event = _build_event("POST", "/entries", body={"image": image_b64})
            response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["entry"]["food_name"] == "Grilled chicken"
        assert body["entry"]["calories"] == 450
        assert body["daily_summary"]["total_calories"] == 450

    def test_post_entries_without_profile_returns_404(self, aws_env_and_table):
        """POST /entries returns 404 if no profile exists."""
        handler = aws_env_and_table

        image_b64 = base64.b64encode(b"fake-image-data").decode()
        event = _build_event("POST", "/entries", body={"image": image_b64})
        response = handler(event, None)

        assert response["statusCode"] == 404

    def test_post_entries_empty_image_returns_400(self, aws_env_and_table):
        """POST /entries with empty image returns 400."""
        handler = aws_env_and_table
        self._create_profile(handler)

        event = _build_event("POST", "/entries", body={"image": ""})
        response = handler(event, None)

        assert response["statusCode"] == 400

    def test_get_summary_with_entries(self, aws_env_and_table):
        """GET /summary returns correct totals after adding entries."""
        handler = aws_env_and_table
        self._create_profile(handler)

        mock_response = _mock_bedrock_response("Pasta", 600, 0.85)

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto3.client.return_value = mock_client

            image_b64 = base64.b64encode(b"fake-image-data").decode()
            handler(_build_event("POST", "/entries", body={"image": image_b64}), None)

        # Get summary for today
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = handler(
            _build_event("GET", "/summary", query_params={"date": today}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_calories"] == 600
        assert len(body["entries"]) == 1
        assert body["entries"][0]["food_name"] == "Pasta"

    def test_get_summary_empty_date(self, aws_env_and_table):
        """GET /summary for a date with no entries returns zero totals."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("GET", "/summary", query_params={"date": "2020-01-01"}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_calories"] == 0
        assert body["entries"] == []

    def test_get_summary_week(self, aws_env_and_table):
        """GET /summary/week returns 7 daily summaries."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("GET", "/summary/week", query_params={"start": "2024-01-15"}),
            None,
        )

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["summaries"]) == 7


# ===========================================================================
# ERROR HANDLING TESTS
# ===========================================================================


class TestErrorHandling:
    """Test HTTP error responses for all error conditions."""

    def _create_profile(self, handler):
        """Helper: create a profile for tests that need one."""
        handler(_build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        }), None)

    def test_400_missing_date_query_param(self, aws_env_and_table):
        """GET /summary without date param returns 400."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("GET", "/summary", query_params={}),
            None,
        )

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "date" in body["error"].lower()

    def test_400_invalid_onboarding_data(self, aws_env_and_table):
        """POST /profile with invalid sex value returns 400."""
        handler = aws_env_and_table
        event = _build_event("POST", "/profile", body={
            "weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "invalid",
            "activity_level": "moderate",
        })
        response = handler(event, None)

        assert response["statusCode"] == 400

    def test_400_weight_out_of_range(self, aws_env_and_table):
        """POST /profile with weight out of range returns 400."""
        handler = aws_env_and_table
        event = _build_event("POST", "/profile", body={
            "weight_kg": 500.0,
            "height_cm": 175.0,
            "age": 30,
            "sex": "male",
            "activity_level": "moderate",
        })
        response = handler(event, None)

        assert response["statusCode"] == 400

    def test_400_goal_out_of_range(self, aws_env_and_table):
        """PUT /profile/goal with goal out of range returns 400."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("PUT", "/profile/goal", body={"daily_calorie_goal": 100}),
            None,
        )

        assert response["statusCode"] == 400

    def test_400_missing_weight_field(self, aws_env_and_table):
        """POST /weight without weight_kg field returns 400."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("POST", "/weight", body={}),
            None,
        )

        assert response["statusCode"] == 400

    def test_400_weight_invalid_value(self, aws_env_and_table):
        """POST /weight with weight out of range returns 400."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("POST", "/weight", body={"weight_kg": 5.0}),
            None,
        )

        assert response["statusCode"] == 400

    def test_404_unknown_route(self, aws_env_and_table):
        """Request to unknown route returns 404."""
        handler = aws_env_and_table
        response = handler(
            _build_event("PATCH", "/entries"),
            None,
        )

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "not found" in body["error"].lower()

    def test_404_profile_not_found_for_summary(self, aws_env_and_table):
        """GET /summary returns 404 when no profile exists."""
        handler = aws_env_and_table
        response = handler(
            _build_event("GET", "/summary", query_params={"date": "2024-01-15"}),
            None,
        )

        assert response["statusCode"] == 404

    def test_409_duplicate_profile(self, aws_env_and_table):
        """POST /profile when profile exists returns 409."""
        handler = aws_env_and_table
        self._create_profile(handler)

        response = handler(
            _build_event("POST", "/profile", body={
                "weight_kg": 80.0,
                "height_cm": 180.0,
                "age": 25,
                "sex": "female",
                "activity_level": "active",
            }),
            None,
        )

        assert response["statusCode"] == 409

    def test_413_image_too_large(self, aws_env_and_table):
        """POST /entries with image exceeding 20MB returns 413."""
        handler = aws_env_and_table
        self._create_profile(handler)

        # Create image data > 20MB (base64 encoded: ~27MB raw → ~20MB decoded)
        large_data = b"x" * (21 * 1024 * 1024)
        large_b64 = base64.b64encode(large_data).decode()

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3"):
            event = _build_event("POST", "/entries", body={"image": large_b64})
            response = handler(event, None)

        assert response["statusCode"] == 413

    def test_503_ai_service_unavailable(self, aws_env_and_table):
        """POST /entries returns 503 when AI service is down."""
        handler = aws_env_and_table
        self._create_profile(handler)

        from botocore.exceptions import EndpointConnectionError

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.side_effect = EndpointConnectionError(
                endpoint_url="https://bedrock.us-east-1.amazonaws.com"
            )
            mock_boto3.client.return_value = mock_client

            # Patch sleep to avoid waiting during retries
            with patch("nutritrack.infrastructure.bedrock_analyzer.asyncio.sleep"):
                image_b64 = base64.b64encode(b"fake-image").decode()
                event = _build_event("POST", "/entries", body={"image": image_b64})
                response = handler(event, None)

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert "retry_after" in body

    def test_cors_headers_on_all_error_responses(self, aws_env_and_table):
        """All error responses include CORS headers."""
        handler = aws_env_and_table

        # 404 error
        response = handler(_build_event("GET", "/nonexistent"), None)
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert response["headers"]["Access-Control-Allow-Methods"] == "GET, POST, PUT, DELETE, OPTIONS"

        # 400 error
        response = handler(_build_event("GET", "/summary", query_params={}), None)
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"


# ===========================================================================
# END-TO-END FLOW TEST
# ===========================================================================


class TestEndToEndFlow:
    """End-to-end flow: onboarding → add entry → get summary."""

    def test_full_user_journey(self, aws_env_and_table):
        """Complete flow: POST /profile → POST /entries → GET /summary.

        Verifies the entire pipeline works together from onboarding
        through food entry to daily summary retrieval.
        """
        handler = aws_env_and_table

        # === Step 1: Verify no profile exists ===
        response = handler(_build_event("GET", "/profile"), None)
        assert response["statusCode"] == 404

        # === Step 2: Complete onboarding ===
        onboarding_response = handler(
            _build_event("POST", "/profile", body={
                "weight_kg": 70.0,
                "height_cm": 168.0,
                "age": 28,
                "sex": "female",
                "activity_level": "light",
            }),
            None,
        )
        assert onboarding_response["statusCode"] == 201
        onboarding_body = json.loads(onboarding_response["body"])
        tdee = onboarding_body["tdee"]
        suggested_goal = onboarding_body["suggested_goal"]
        assert tdee > 0
        assert suggested_goal > 0
        assert suggested_goal < tdee  # deficit applied

        # === Step 3: Verify profile is accessible ===
        profile_response = handler(_build_event("GET", "/profile"), None)
        assert profile_response["statusCode"] == 200
        profile_body = json.loads(profile_response["body"])
        assert profile_body["weight_kg"] == 70.0
        assert profile_body["daily_calorie_goal"] == suggested_goal

        # === Step 4: Add a food entry ===
        mock_response = _mock_bedrock_response("Greek salad", 320, 0.92)

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto3.client.return_value = mock_client

            image_b64 = base64.b64encode(b"salad-photo").decode()
            entry_response = handler(
                _build_event("POST", "/entries", body={"image": image_b64}),
                None,
            )

        assert entry_response["statusCode"] == 201
        entry_body = json.loads(entry_response["body"])
        assert entry_body["entry"]["food_name"] == "Greek salad"
        assert entry_body["entry"]["calories"] == 320
        assert entry_body["daily_summary"]["total_calories"] == 320

        # === Step 5: Add a second food entry ===
        mock_response2 = _mock_bedrock_response("Grilled salmon", 550, 0.88)

        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response2
            mock_boto3.client.return_value = mock_client

            image_b64 = base64.b64encode(b"salmon-photo").decode()
            entry_response2 = handler(
                _build_event("POST", "/entries", body={"image": image_b64}),
                None,
            )

        assert entry_response2["statusCode"] == 201
        entry_body2 = json.loads(entry_response2["body"])
        assert entry_body2["entry"]["food_name"] == "Grilled salmon"
        assert entry_body2["daily_summary"]["total_calories"] == 320 + 550

        # === Step 6: Get daily summary ===
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        summary_response = handler(
            _build_event("GET", "/summary", query_params={"date": today}),
            None,
        )

        assert summary_response["statusCode"] == 200
        summary_body = json.loads(summary_response["body"])
        assert summary_body["total_calories"] == 870  # 320 + 550
        assert len(summary_body["entries"]) == 2
        assert summary_body["remaining_calories"] == max(0, suggested_goal - 870)
        # Goal status depends on whether 870 <= suggested_goal
        if 870 <= suggested_goal:
            assert summary_body["status"] == "within_goal"
        else:
            assert summary_body["status"] == "exceeded"

        # === Step 7: Update weight ===
        weight_response = handler(
            _build_event("POST", "/weight", body={"weight_kg": 69.5}),
            None,
        )
        assert weight_response["statusCode"] == 200
        weight_body = json.loads(weight_response["body"])
        assert weight_body["new_tdee"] > 0
        # TDEE should be slightly lower with less weight
        assert weight_body["new_tdee"] <= tdee

        # === Step 8: Verify weight history ===
        history_response = handler(
            _build_event("GET", "/weight/history", query_params={"limit": "10"}),
            None,
        )
        assert history_response["statusCode"] == 200
        history_body = json.loads(history_response["body"])
        # Should have the initial weight from onboarding + the update (may be same date)
        assert len(history_body["records"]) >= 1
        weights = [r["weight_kg"] for r in history_body["records"]]
        assert 69.5 in weights
