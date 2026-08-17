"""Amazon Bedrock Nova Lite adapter for food image analysis."""

import asyncio
import json

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

from nutritrack.use_cases.exceptions import AIServiceUnavailableError, FoodNotRecognizedError
from nutritrack.use_cases.results import FoodAnalysisResult


SYSTEM_PROMPT = """You are a food recognition and macronutrient estimation assistant.
Analyze the provided food image and respond with ONLY a JSON object:
{
    "food_name": "descriptive name of the food",
    "estimated_calories": <integer calories>,
    "protein_g": <float grams of protein>,
    "carbs_g": <float grams of carbohydrates>,
    "fat_g": <float grams of fat>,
    "confidence": <float 0.0-1.0>
}

Rules:
- Estimate calories and macros for the visible portion size
- If multiple items, sum total calories/macros and list all foods
- If not food, respond: {"food_name": "not_food", "estimated_calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "confidence": 0.0}
- Be conservative with estimates (prefer slight overestimation)
- Protein, carbs, fat should be reasonable (protein*4 + carbs*4 + fat*9 ≈ calories)
"""

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1

# Default model ID for Amazon Nova Lite
DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"


class BedrockImageAnalyzer:
    """Adapter: Amazon Bedrock Nova Lite for food recognition."""

    def __init__(self, region: str = "us-east-1", model_id: str = DEFAULT_MODEL_ID):
        self.model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    @staticmethod
    def _detect_format(image_data: bytes) -> str:
        """Detect image format from magic bytes. Defaults to jpeg."""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "png"
        if image_data[:3] == b'GIF':
            return "gif"
        if image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "webp"
        # Default to jpeg (covers JFIF and EXIF headers)
        return "jpeg"

    async def analyze_food_image(self, image_data: bytes) -> FoodAnalysisResult:
        """Analyze a food image and return structured calorie estimation.

        Sends the image as base64 to Bedrock's Nova Lite model via the
        Converse API, parses the JSON response, validates it, and returns
        a FoodAnalysisResult.

        Raises:
            FoodNotRecognizedError: If the model identifies the image as not food.
            AIServiceUnavailableError: If the API is unreachable after retries.
        """
        # Detect image format from magic bytes
        image_format = self._detect_format(image_data)

        # Build the Converse API request body
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": image_format,
                            "source": {
                                "bytes": image_data,
                            },
                        },
                    },
                    {
                        "text": "Analyze this food image and estimate calories.",
                    },
                ],
            },
        ]

        system = [{"text": SYSTEM_PROMPT}]

        response_text = await self._call_with_retry(messages, system)
        return self._parse_response(response_text)

    async def _call_with_retry(self, messages: list[dict], system: list[dict]) -> str:
        """Call Bedrock Converse API with exponential backoff retry."""
        last_exception: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=system,
                    inferenceConfig={
                        "maxTokens": 200,
                        "temperature": 0.1,
                    },
                )
                # Extract text from the response
                output = response.get("output", {})
                message = output.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if "text" in block:
                        return block["text"]
                return ""

            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code in ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"):
                    last_exception = exc
                    if attempt < MAX_RETRIES - 1:
                        wait_time = BACKOFF_BASE_SECONDS * (2**attempt)
                        await asyncio.sleep(wait_time)
                else:
                    raise AIServiceUnavailableError(
                        f"Bedrock API error: {error_code} — {exc}"
                    )
            except EndpointConnectionError as exc:
                last_exception = exc
                if attempt < MAX_RETRIES - 1:
                    wait_time = BACKOFF_BASE_SECONDS * (2**attempt)
                    await asyncio.sleep(wait_time)

        raise AIServiceUnavailableError(
            f"Bedrock API unavailable after {MAX_RETRIES} retries: {last_exception}"
        )

    def _parse_response(self, response_text: str) -> FoodAnalysisResult:
        """Parse and validate the JSON response from the model.

        Raises:
            FoodNotRecognizedError: If food_name is "not_food".
            AIServiceUnavailableError: If response cannot be parsed or is invalid.
        """
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (code fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIServiceUnavailableError(
                f"Failed to parse AI response as JSON: {exc}"
            )

        food_name = data.get("food_name", "")
        estimated_calories = data.get("estimated_calories", -1)
        protein_g = data.get("protein_g", 0.0)
        carbs_g = data.get("carbs_g", 0.0)
        fat_g = data.get("fat_g", 0.0)
        confidence = data.get("confidence", -1.0)

        # Validate food_name
        if not isinstance(food_name, str) or not food_name.strip():
            raise AIServiceUnavailableError(
                "Invalid AI response: food_name is empty or not a string"
            )

        # Check for "not_food" response
        if food_name.strip().lower() == "not_food":
            raise FoodNotRecognizedError("Image does not contain recognizable food")

        # Validate calories
        if not isinstance(estimated_calories, (int, float)) or estimated_calories < 0:
            raise AIServiceUnavailableError(
                f"Invalid AI response: estimated_calories must be >= 0, got {estimated_calories}"
            )

        # Validate confidence
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            raise AIServiceUnavailableError(
                f"Invalid AI response: confidence must be 0-1, got {confidence}"
            )

        # Ensure macros are non-negative floats
        protein_g = max(0.0, float(protein_g)) if isinstance(protein_g, (int, float)) else 0.0
        carbs_g = max(0.0, float(carbs_g)) if isinstance(carbs_g, (int, float)) else 0.0
        fat_g = max(0.0, float(fat_g)) if isinstance(fat_g, (int, float)) else 0.0

        return FoodAnalysisResult(
            food_name=food_name.strip(),
            estimated_calories=int(estimated_calories),
            protein_g=round(protein_g, 1),
            carbs_g=round(carbs_g, 1),
            fat_g=round(fat_g, 1),
            confidence=float(confidence),
        )
