"""Integration tests for DynamoDB repository implementations using moto."""

import asyncio

import boto3
import pytest
from moto import mock_aws

from nutritrack.domain.models import (
    ActivityLevel,
    FoodEntry,
    Sex,
    UserProfile,
    WeightRecord,
)
from nutritrack.infrastructure.dynamodb import (
    DynamoDBEntryRepository,
    DynamoDBUserProfileRepository,
)

TABLE_NAME = "nutritrack-entries"


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
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
        table.wait_until_exists()
        yield table


@pytest.fixture
def entry_repo(dynamodb_table):
    """Create an entry repository with mocked DynamoDB."""
    return DynamoDBEntryRepository(TABLE_NAME)


@pytest.fixture
def profile_repo(dynamodb_table):
    """Create a profile repository with mocked DynamoDB."""
    return DynamoDBUserProfileRepository(TABLE_NAME)


# --- DynamoDBEntryRepository tests ---


class TestDynamoDBEntryRepository:
    @pytest.mark.asyncio
    async def test_save_and_get_entry(self, entry_repo):
        entry = FoodEntry(
            entry_id="abc123",
            food_name="Grilled chicken salad",
            calories=450,
            confidence=0.87,
            timestamp="2024-01-15T12:30:00Z",
            date="2024-01-15",
        )

        await entry_repo.save_entry(entry)
        entries = await entry_repo.get_entries_by_date("2024-01-15")

        assert len(entries) == 1
        assert entries[0].entry_id == "abc123"
        assert entries[0].food_name == "Grilled chicken salad"
        assert entries[0].calories == 450
        assert entries[0].confidence == pytest.approx(0.87)
        assert entries[0].timestamp == "2024-01-15T12:30:00Z"
        assert entries[0].date == "2024-01-15"

    @pytest.mark.asyncio
    async def test_get_entries_empty_date(self, entry_repo):
        entries = await entry_repo.get_entries_by_date("2024-01-20")
        assert entries == []

    @pytest.mark.asyncio
    async def test_multiple_entries_same_date(self, entry_repo):
        entry1 = FoodEntry(
            entry_id="id1",
            food_name="Oatmeal",
            calories=300,
            confidence=0.92,
            timestamp="2024-01-15T08:00:00Z",
            date="2024-01-15",
        )
        entry2 = FoodEntry(
            entry_id="id2",
            food_name="Pasta",
            calories=600,
            confidence=0.75,
            timestamp="2024-01-15T13:00:00Z",
            date="2024-01-15",
        )

        await entry_repo.save_entry(entry1)
        await entry_repo.save_entry(entry2)

        entries = await entry_repo.get_entries_by_date("2024-01-15")
        assert len(entries) == 2
        entry_ids = {e.entry_id for e in entries}
        assert entry_ids == {"id1", "id2"}

    @pytest.mark.asyncio
    async def test_entries_isolated_by_date(self, entry_repo):
        entry_jan15 = FoodEntry(
            entry_id="id1",
            food_name="Oatmeal",
            calories=300,
            confidence=0.92,
            timestamp="2024-01-15T08:00:00Z",
            date="2024-01-15",
        )
        entry_jan16 = FoodEntry(
            entry_id="id2",
            food_name="Pasta",
            calories=600,
            confidence=0.75,
            timestamp="2024-01-16T13:00:00Z",
            date="2024-01-16",
        )

        await entry_repo.save_entry(entry_jan15)
        await entry_repo.save_entry(entry_jan16)

        entries_15 = await entry_repo.get_entries_by_date("2024-01-15")
        entries_16 = await entry_repo.get_entries_by_date("2024-01-16")

        assert len(entries_15) == 1
        assert entries_15[0].entry_id == "id1"
        assert len(entries_16) == 1
        assert entries_16[0].entry_id == "id2"


# --- DynamoDBUserProfileRepository tests ---


class TestDynamoDBUserProfileRepository:
    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, profile_repo):
        profile = await profile_repo.get_profile()
        assert profile is None

    @pytest.mark.asyncio
    async def test_save_and_get_profile(self, profile_repo):
        profile = UserProfile(
            weight_kg=78.5,
            height_cm=175.0,
            age=30,
            sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE,
            daily_calorie_goal=1850,
            tdee=2250,
        )

        await profile_repo.save_profile(profile)
        loaded = await profile_repo.get_profile()

        assert loaded is not None
        assert loaded.weight_kg == pytest.approx(78.5)
        assert loaded.height_cm == pytest.approx(175.0)
        assert loaded.age == 30
        assert loaded.sex == Sex.MALE
        assert loaded.activity_level == ActivityLevel.MODERATE
        assert loaded.daily_calorie_goal == 1850
        assert loaded.tdee == 2250

    @pytest.mark.asyncio
    async def test_save_profile_overwrites(self, profile_repo):
        profile1 = UserProfile(
            weight_kg=78.5,
            height_cm=175.0,
            age=30,
            sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE,
            daily_calorie_goal=1850,
            tdee=2250,
        )
        profile2 = UserProfile(
            weight_kg=76.0,
            height_cm=175.0,
            age=30,
            sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE,
            daily_calorie_goal=1800,
            tdee=2200,
        )

        await profile_repo.save_profile(profile1)
        await profile_repo.save_profile(profile2)
        loaded = await profile_repo.get_profile()

        assert loaded is not None
        assert loaded.weight_kg == pytest.approx(76.0)
        assert loaded.daily_calorie_goal == 1800

    @pytest.mark.asyncio
    async def test_save_and_get_weight_record(self, profile_repo):
        record = WeightRecord(date="2024-01-15", weight_kg=78.5)

        await profile_repo.save_weight_record(record)
        history = await profile_repo.get_weight_history()

        assert len(history) == 1
        assert history[0].date == "2024-01-15"
        assert history[0].weight_kg == pytest.approx(78.5)

    @pytest.mark.asyncio
    async def test_weight_history_ordered_descending(self, profile_repo):
        records = [
            WeightRecord(date="2024-01-10", weight_kg=80.0),
            WeightRecord(date="2024-01-12", weight_kg=79.5),
            WeightRecord(date="2024-01-15", weight_kg=78.5),
        ]
        for r in records:
            await profile_repo.save_weight_record(r)

        history = await profile_repo.get_weight_history()

        assert len(history) == 3
        # ScanIndexForward=False means descending SK order
        assert history[0].date == "2024-01-15"
        assert history[1].date == "2024-01-12"
        assert history[2].date == "2024-01-10"

    @pytest.mark.asyncio
    async def test_weight_history_respects_limit(self, profile_repo):
        for day in range(1, 11):
            record = WeightRecord(date=f"2024-01-{day:02d}", weight_kg=80.0 - day * 0.2)
            await profile_repo.save_weight_record(record)

        history = await profile_repo.get_weight_history(limit=3)

        assert len(history) == 3
        # Most recent 3
        assert history[0].date == "2024-01-10"
        assert history[1].date == "2024-01-09"
        assert history[2].date == "2024-01-08"

    @pytest.mark.asyncio
    async def test_female_profile(self, profile_repo):
        """Test that female sex enum serializes/deserializes correctly."""
        profile = UserProfile(
            weight_kg=60.0,
            height_cm=165.0,
            age=25,
            sex=Sex.FEMALE,
            activity_level=ActivityLevel.ACTIVE,
            daily_calorie_goal=1700,
            tdee=2100,
        )

        await profile_repo.save_profile(profile)
        loaded = await profile_repo.get_profile()

        assert loaded is not None
        assert loaded.sex == Sex.FEMALE
        assert loaded.activity_level == ActivityLevel.ACTIVE
