"""DynamoDB repository implementations using single-table design.

Table: nutritrack-entries
PK: USER#default
SK patterns:
  - PROFILE                         → UserProfile
  - WEIGHT#YYYY-MM-DD               → WeightRecord
  - DATE#YYYY-MM-DD#ENTRY#uuid      → FoodEntry
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import boto3

from nutritrack.domain.models import (
    ActivityLevel,
    FoodEntry,
    Sex,
    UserProfile,
    WeightRecord,
)

# Constants for single-table design
_PK = "USER#default"
_SK_PROFILE = "PROFILE"
_SK_WEIGHT_PREFIX = "WEIGHT#"
_SK_DATE_PREFIX = "DATE#"
_SK_ENTRY_INFIX = "#ENTRY#"


# --- Serialization helpers ---


def _sex_to_str(sex: Sex) -> str:
    return sex.value


def _str_to_sex(value: str) -> Sex:
    return Sex(value)


def _activity_level_to_str(level: ActivityLevel) -> str:
    return level.value


def _str_to_activity_level(value: str) -> ActivityLevel:
    return ActivityLevel(value)


def _to_decimal(value: float | int) -> Decimal:
    """Convert a Python float/int to Decimal for DynamoDB."""
    return Decimal(str(value))


def _from_decimal(value: Decimal) -> float:
    """Convert a DynamoDB Decimal back to Python float."""
    return float(value)


def _serialize_profile(profile: UserProfile) -> dict:
    """Serialize a UserProfile to a DynamoDB item dict."""
    return {
        "PK": _PK,
        "SK": _SK_PROFILE,
        "weight_kg": _to_decimal(profile.weight_kg),
        "height_cm": _to_decimal(profile.height_cm),
        "age": profile.age,
        "sex": _sex_to_str(profile.sex),
        "activity_level": _activity_level_to_str(profile.activity_level),
        "daily_calorie_goal": profile.daily_calorie_goal,
        "tdee": profile.tdee,
    }


def _deserialize_profile(item: dict) -> UserProfile:
    """Deserialize a DynamoDB item dict to a UserProfile."""
    return UserProfile(
        weight_kg=_from_decimal(item["weight_kg"]),
        height_cm=_from_decimal(item["height_cm"]),
        age=int(item["age"]),
        sex=_str_to_sex(item["sex"]),
        activity_level=_str_to_activity_level(item["activity_level"]),
        daily_calorie_goal=int(item["daily_calorie_goal"]),
        tdee=int(item["tdee"]),
    )


def _serialize_weight_record(record: WeightRecord) -> dict:
    """Serialize a WeightRecord to a DynamoDB item dict."""
    return {
        "PK": _PK,
        "SK": f"{_SK_WEIGHT_PREFIX}{record.date}",
        "weight_kg": _to_decimal(record.weight_kg),
        "created_at": record.date,
    }


def _deserialize_weight_record(item: dict) -> WeightRecord:
    """Deserialize a DynamoDB item dict to a WeightRecord."""
    sk: str = item["SK"]
    date = sk.removeprefix(_SK_WEIGHT_PREFIX)
    return WeightRecord(
        date=date,
        weight_kg=_from_decimal(item["weight_kg"]),
    )


def _serialize_food_entry(entry: FoodEntry) -> dict:
    """Serialize a FoodEntry to a DynamoDB item dict."""
    sk = f"{_SK_DATE_PREFIX}{entry.date}{_SK_ENTRY_INFIX}{entry.entry_id}"
    return {
        "PK": _PK,
        "SK": sk,
        "food_name": entry.food_name,
        "calories": entry.calories,
        "protein_g": _to_decimal(entry.protein_g),
        "carbs_g": _to_decimal(entry.carbs_g),
        "fat_g": _to_decimal(entry.fat_g),
        "confidence": _to_decimal(entry.confidence),
        "timestamp": entry.timestamp,
    }


def _deserialize_food_entry(item: dict) -> FoodEntry:
    """Deserialize a DynamoDB item dict to a FoodEntry."""
    sk: str = item["SK"]
    # SK format: DATE#YYYY-MM-DD#ENTRY#uuid
    parts = sk.split("#")
    # parts = ["DATE", "YYYY-MM-DD", "ENTRY", "uuid"]
    date = parts[1]
    entry_id = parts[3]
    return FoodEntry(
        entry_id=entry_id,
        food_name=item["food_name"],
        calories=int(item["calories"]),
        protein_g=_from_decimal(item.get("protein_g", 0)),
        carbs_g=_from_decimal(item.get("carbs_g", 0)),
        fat_g=_from_decimal(item.get("fat_g", 0)),
        confidence=_from_decimal(item["confidence"]),
        timestamp=item["timestamp"],
        date=date,
    )


# --- Repository implementations ---


class DynamoDBEntryRepository:
    """Adapter: DynamoDB for food entry persistence."""

    def __init__(self, table_name: str):
        self._table_name = table_name
        dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    async def save_entry(self, entry: FoodEntry) -> None:
        """PutItem for a food entry."""
        item = _serialize_food_entry(entry)
        self._table.put_item(Item=item)

    async def get_entries_by_date(self, date: str) -> list[FoodEntry]:
        """Query all food entries for a given date using begins_with on SK."""
        prefix = f"{_SK_DATE_PREFIX}{date}{_SK_ENTRY_INFIX}"
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": _PK,
                ":sk_prefix": prefix,
            },
        )
        items = response.get("Items", [])
        return [_deserialize_food_entry(item) for item in items]

    async def delete_entry(self, date: str, entry_id: str) -> bool:
        """Delete a food entry by date and entry_id. Returns True if deleted."""
        sk = f"{_SK_DATE_PREFIX}{date}{_SK_ENTRY_INFIX}{entry_id}"
        self._table.delete_item(Key={"PK": _PK, "SK": sk})
        return True


class DynamoDBUserProfileRepository:
    """Adapter: DynamoDB for user profile and weight history."""

    def __init__(self, table_name: str):
        self._table_name = table_name
        dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(table_name)

    async def get_profile(self) -> Optional[UserProfile]:
        """GetItem PK=USER#default, SK=PROFILE."""
        response = self._table.get_item(
            Key={"PK": _PK, "SK": _SK_PROFILE},
        )
        item = response.get("Item")
        if item is None:
            return None
        return _deserialize_profile(item)

    async def save_profile(self, profile: UserProfile) -> None:
        """PutItem PK=USER#default, SK=PROFILE."""
        item = _serialize_profile(profile)
        self._table.put_item(Item=item)

    async def save_weight_record(self, record: WeightRecord) -> None:
        """PutItem PK=USER#default, SK=WEIGHT#YYYY-MM-DD."""
        item = _serialize_weight_record(record)
        self._table.put_item(Item=item)

    async def get_weight_history(self, limit: int = 30) -> list[WeightRecord]:
        """Query PK=USER#default, SK begins_with WEIGHT#, ScanIndexForward=False."""
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": _PK,
                ":sk_prefix": _SK_WEIGHT_PREFIX,
            },
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response.get("Items", [])
        return [_deserialize_weight_record(item) for item in items]
