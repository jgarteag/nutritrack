"""Unit tests for the BedrockImageAnalyzer infrastructure adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from nutritrack.infrastructure.bedrock_analyzer import (
    BedrockImageAnalyzer,
    SYSTEM_PROMPT,
    MAX_RETRIES,
)
from nutritrack.use_cases.exceptions import AIServiceUnavailableError, FoodNotRecognizedError
from nutritrack.use_cases.results import FoodAnalysisResult


def _make_converse_response(content: str) -> dict:
    """Helper to build a Bedrock Converse API response."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": content}],
            }
        },
        "stopReason": "end_turn",
    }


@pytest.fixture
def analyzer():
    """Create a BedrockImageAnalyzer with mocked boto3 client."""
    with patch("nutritrack.infrastructure.bedrock_analyzer.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        a = BedrockImageAnalyzer(region="us-east-1")
        a._client = mock_client
        yield a


@pytest.fixture
def sample_image():
    """Sample image bytes."""
    return b"\x89PNG\r\n\x1a\nfake_image_data"


class TestAnalyzeFoodImage:
    """Tests for the analyze_food_image method."""

    async def test_successful_analysis(self, analyzer, sample_image):
        """Valid food response is parsed correctly."""
        response_json = json.dumps({
            "food_name": "Grilled chicken salad",
            "estimated_calories": 450,
            "confidence": 0.87,
        })
        analyzer._client.converse.return_value = _make_converse_response(response_json)

        result = await analyzer.analyze_food_image(sample_image)

        assert result.food_name == "Grilled chicken salad"
        assert result.estimated_calories == 450
        assert result.confidence == 0.87

    async def test_zero_calories_is_valid(self, analyzer, sample_image):
        """Zero calories should be accepted as valid."""
        response_json = json.dumps({
            "food_name": "Black coffee",
            "estimated_calories": 0,
            "confidence": 0.95,
        })
        analyzer._client.converse.return_value = _make_converse_response(response_json)

        result = await analyzer.analyze_food_image(sample_image)

        assert result.food_name == "Black coffee"
        assert result.estimated_calories == 0
        assert result.confidence == 0.95

    async def test_not_food_raises_error(self, analyzer, sample_image):
        """When model returns 'not_food', FoodNotRecognizedError is raised."""
        response_json = json.dumps({
            "food_name": "not_food",
            "estimated_calories": 0,
            "confidence": 0.0,
        })
        analyzer._client.converse.return_value = _make_converse_response(response_json)

        with pytest.raises(FoodNotRecognizedError):
            await analyzer.analyze_food_image(sample_image)

    async def test_not_food_case_insensitive(self, analyzer, sample_image):
        """'Not_Food' (mixed case) still raises FoodNotRecognizedError."""
        response_json = json.dumps({
            "food_name": "Not_Food",
            "estimated_calories": 0,
            "confidence": 0.0,
        })
        analyzer._client.converse.return_value = _make_converse_response(response_json)

        with pytest.raises(FoodNotRecognizedError):
            await analyzer.analyze_food_image(sample_image)

    async def test_image_sent_as_bytes_in_request(self, analyzer, sample_image):
        """Image data is sent as raw bytes to Bedrock Converse API."""
        response_json = json.dumps({
            "food_name": "Pizza",
            "estimated_calories": 300,
            "confidence": 0.9,
        })
        analyzer._client.converse.return_value = _make_converse_response(response_json)

        await analyzer.analyze_food_image(sample_image)

        call_args = analyzer._client.converse.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_message = messages[0]
        image_content = user_message["content"][0]
        assert "image" in image_content
        assert image_content["image"]["source"]["bytes"] == sample_image

    async def test_response_with_markdown_fences(self, analyzer, sample_image):
        """Model response wrapped in markdown code fences is still parsed."""
        response_text = '```json\n{"food_name": "Burger", "estimated_calories": 600, "confidence": 0.85}\n```'
        analyzer._client.converse.return_value = _make_converse_response(response_text)

        result = await analyzer.analyze_food_image(sample_image)

        assert result.food_name == "Burger"
        assert result.estimated_calories == 600


class TestResponseParsing:
    """Tests for _parse_response validation logic."""

    @pytest.fixture
    def analyzer_instance(self):
        with patch("nutritrack.infrastructure.bedrock_analyzer.boto3"):
            return BedrockImageAnalyzer()

    def test_invalid_json_raises_service_error(self, analyzer_instance):
        """Non-JSON response raises AIServiceUnavailableError."""
        with pytest.raises(AIServiceUnavailableError, match="Failed to parse"):
            analyzer_instance._parse_response("this is not json")

    def test_negative_calories_raises_error(self, analyzer_instance):
        """Negative calories are rejected."""
        response_json = json.dumps({
            "food_name": "Pizza",
            "estimated_calories": -100,
            "confidence": 0.8,
        })
        with pytest.raises(AIServiceUnavailableError, match="estimated_calories"):
            analyzer_instance._parse_response(response_json)

    def test_confidence_above_one_raises_error(self, analyzer_instance):
        """Confidence > 1 is rejected."""
        response_json = json.dumps({
            "food_name": "Pizza",
            "estimated_calories": 300,
            "confidence": 1.5,
        })
        with pytest.raises(AIServiceUnavailableError, match="confidence"):
            analyzer_instance._parse_response(response_json)

    def test_confidence_below_zero_raises_error(self, analyzer_instance):
        """Confidence < 0 is rejected."""
        response_json = json.dumps({
            "food_name": "Pizza",
            "estimated_calories": 300,
            "confidence": -0.1,
        })
        with pytest.raises(AIServiceUnavailableError, match="confidence"):
            analyzer_instance._parse_response(response_json)

    def test_empty_food_name_raises_error(self, analyzer_instance):
        """Empty food_name is rejected."""
        response_json = json.dumps({
            "food_name": "",
            "estimated_calories": 300,
            "confidence": 0.8,
        })
        with pytest.raises(AIServiceUnavailableError, match="food_name"):
            analyzer_instance._parse_response(response_json)

    def test_boundary_confidence_zero(self, analyzer_instance):
        """Confidence of exactly 0.0 is valid."""
        response_json = json.dumps({
            "food_name": "Unknown item",
            "estimated_calories": 100,
            "confidence": 0.0,
        })
        result = analyzer_instance._parse_response(response_json)
        assert result.confidence == 0.0

    def test_boundary_confidence_one(self, analyzer_instance):
        """Confidence of exactly 1.0 is valid."""
        response_json = json.dumps({
            "food_name": "Water",
            "estimated_calories": 0,
            "confidence": 1.0,
        })
        result = analyzer_instance._parse_response(response_json)
        assert result.confidence == 1.0


class TestRetryBehavior:
    """Tests for exponential backoff retry logic."""

    async def test_retries_on_throttling(self, analyzer, sample_image):
        """Retries on ThrottlingException and succeeds on subsequent attempt."""
        response_json = json.dumps({
            "food_name": "Burger",
            "estimated_calories": 600,
            "confidence": 0.85,
        })

        throttling_error = ClientError(
            error_response={"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            operation_name="Converse",
        )

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise throttling_error
            return _make_converse_response(response_json)

        analyzer._client.converse.side_effect = side_effect

        mock_sleep = AsyncMock()
        with patch("nutritrack.infrastructure.bedrock_analyzer.asyncio.sleep", mock_sleep):
            result = await analyzer.analyze_food_image(sample_image)

        assert result.food_name == "Burger"
        assert call_count == 2
        mock_sleep.assert_called_once_with(1)  # First backoff: 1s

    async def test_retries_on_connection_error(self, analyzer, sample_image):
        """Retries on EndpointConnectionError."""
        response_json = json.dumps({
            "food_name": "Pasta",
            "estimated_calories": 500,
            "confidence": 0.8,
        })

        connection_error = EndpointConnectionError(endpoint_url="https://bedrock.us-east-1.amazonaws.com")

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise connection_error
            return _make_converse_response(response_json)

        analyzer._client.converse.side_effect = side_effect

        mock_sleep = AsyncMock()
        with patch("nutritrack.infrastructure.bedrock_analyzer.asyncio.sleep", mock_sleep):
            result = await analyzer.analyze_food_image(sample_image)

        assert result.food_name == "Pasta"
        assert call_count == 3
        assert mock_sleep.call_args_list[0][0] == (1,)
        assert mock_sleep.call_args_list[1][0] == (2,)

    async def test_raises_after_max_retries(self, analyzer, sample_image):
        """Raises AIServiceUnavailableError after all retries exhausted."""
        throttling_error = ClientError(
            error_response={"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            operation_name="Converse",
        )

        analyzer._client.converse.side_effect = throttling_error

        mock_sleep = AsyncMock()
        with patch("nutritrack.infrastructure.bedrock_analyzer.asyncio.sleep", mock_sleep):
            with pytest.raises(AIServiceUnavailableError, match="3 retries"):
                await analyzer.analyze_food_image(sample_image)

    async def test_non_retryable_error_raises_immediately(self, analyzer, sample_image):
        """Non-retryable ClientErrors raise immediately without retry."""
        access_denied = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
            operation_name="Converse",
        )

        analyzer._client.converse.side_effect = access_denied

        with pytest.raises(AIServiceUnavailableError, match="AccessDeniedException"):
            await analyzer.analyze_food_image(sample_image)

        # Should only be called once (no retries)
        assert analyzer._client.converse.call_count == 1
