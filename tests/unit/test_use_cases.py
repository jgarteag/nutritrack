"""Unit tests for application layer use cases."""

from typing import Optional

import pytest

from nutritrack.domain.models import (
    ActivityLevel,
    DailyGoal,
    FoodEntry,
    GoalStatus,
    Sex,
    UserProfile,
    WeightRecord,
    calculate_tdee,
    suggest_calorie_goal,
)
from nutritrack.use_cases.add_food_entry import add_food_entry
from nutritrack.use_cases.complete_onboarding import complete_onboarding
from nutritrack.use_cases.exceptions import FoodNotRecognizedError, InvalidImageError
from nutritrack.use_cases.get_daily_summary import get_daily_summary
from nutritrack.use_cases.ports import EntryRepository, ImageAnalyzer, UserProfileRepository
from nutritrack.use_cases.results import FoodAnalysisResult
from nutritrack.use_cases.update_weight import update_weight


# ---------------------------------------------------------------------------
# Mock implementations of Protocol ports
# ---------------------------------------------------------------------------


class MockImageAnalyzer:
    """Mock implementation of ImageAnalyzer port."""

    def __init__(
        self,
        result: Optional[FoodAnalysisResult] = None,
        raise_error: Optional[Exception] = None,
    ):
        self.result = result or FoodAnalysisResult(
            food_name="Grilled Chicken Salad",
            estimated_calories=450,
            protein_g=35.0,
            carbs_g=20.0,
            fat_g=15.0,
            confidence=0.85,
        )
        self.raise_error = raise_error
        self.calls: list[bytes] = []

    async def analyze_food_image(self, image_data: bytes) -> FoodAnalysisResult:
        self.calls.append(image_data)
        if self.raise_error:
            raise self.raise_error
        return self.result


class MockEntryRepository:
    """Mock implementation of EntryRepository port."""

    def __init__(self, entries: Optional[list[FoodEntry]] = None):
        self.entries: list[FoodEntry] = entries or []
        self.saved_entries: list[FoodEntry] = []

    async def save_entry(self, entry: FoodEntry) -> None:
        self.saved_entries.append(entry)
        self.entries.append(entry)

    async def get_entries_by_date(self, date: str) -> list[FoodEntry]:
        return [e for e in self.entries if e.date == date]


class MockUserProfileRepository:
    """Mock implementation of UserProfileRepository port."""

    def __init__(
        self,
        profile: Optional[UserProfile] = None,
        weight_history: Optional[list[WeightRecord]] = None,
    ):
        self.profile = profile
        self.weight_history: list[WeightRecord] = weight_history or []
        self.saved_profiles: list[UserProfile] = []
        self.saved_weight_records: list[WeightRecord] = []

    async def get_profile(self) -> Optional[UserProfile]:
        return self.profile

    async def save_profile(self, profile: UserProfile) -> None:
        self.saved_profiles.append(profile)
        self.profile = profile

    async def save_weight_record(self, record: WeightRecord) -> None:
        self.saved_weight_records.append(record)
        self.weight_history.append(record)

    async def get_weight_history(self, limit: int = 30) -> list[WeightRecord]:
        return self.weight_history[:limit]


# ---------------------------------------------------------------------------
# add_food_entry tests
# ---------------------------------------------------------------------------


class TestAddFoodEntry:
    """Tests for add_food_entry use case."""

    async def test_happy_path(self):
        """Valid image produces a saved entry and correct daily summary."""
        analyzer = MockImageAnalyzer()
        repo = MockEntryRepository()
        goal = DailyGoal(target_calories=2000)
        image_data = b"\x89PNG" + b"\x00" * 100

        result = await add_food_entry(image_data, analyzer, repo, goal)

        # Entry was created with correct food info
        assert result.entry.food_name == "Grilled Chicken Salad"
        assert result.entry.calories == 450
        assert result.entry.confidence == 0.85

        # Entry was persisted
        assert len(repo.saved_entries) == 1
        assert repo.saved_entries[0].entry_id == result.entry.entry_id

        # Daily summary reflects the new entry
        assert result.daily_summary.total_calories == 450
        assert result.daily_summary.remaining_calories == 2000 - 450
        assert result.daily_summary.status == GoalStatus.WITHIN_GOAL

    async def test_empty_image_raises_invalid_image_error(self):
        """Empty image data raises InvalidImageError."""
        analyzer = MockImageAnalyzer()
        repo = MockEntryRepository()
        goal = DailyGoal(target_calories=2000)

        with pytest.raises(InvalidImageError):
            await add_food_entry(b"", analyzer, repo, goal)

        # Analyzer should not be called
        assert len(analyzer.calls) == 0

    async def test_image_too_large_raises_invalid_image_error(self):
        """Image exceeding 20MB raises InvalidImageError."""
        analyzer = MockImageAnalyzer()
        repo = MockEntryRepository()
        goal = DailyGoal(target_calories=2000)
        oversized_image = b"\x00" * (20 * 1024 * 1024 + 1)

        with pytest.raises(InvalidImageError):
            await add_food_entry(oversized_image, analyzer, repo, goal)

        # Analyzer should not be called
        assert len(analyzer.calls) == 0

    async def test_food_not_recognized_raises_error(self):
        """When AI cannot recognize food, FoodNotRecognizedError propagates."""
        analyzer = MockImageAnalyzer(
            raise_error=FoodNotRecognizedError("No food detected in image")
        )
        repo = MockEntryRepository()
        goal = DailyGoal(target_calories=2000)
        image_data = b"\x89PNG" + b"\x00" * 100

        with pytest.raises(FoodNotRecognizedError):
            await add_food_entry(image_data, analyzer, repo, goal)

        # No entry should be saved
        assert len(repo.saved_entries) == 0


# ---------------------------------------------------------------------------
# get_daily_summary tests
# ---------------------------------------------------------------------------


class TestGetDailySummary:
    """Tests for get_daily_summary use case."""

    async def test_entries_exist(self):
        """Date with entries returns correct summary with totals."""
        entries = [
            FoodEntry(
                entry_id="1",
                food_name="Oatmeal",
                calories=300,
                confidence=0.9,
                timestamp="2024-01-15T08:00:00Z",
                date="2024-01-15",
            ),
            FoodEntry(
                entry_id="2",
                food_name="Chicken Salad",
                calories=500,
                confidence=0.85,
                timestamp="2024-01-15T12:30:00Z",
                date="2024-01-15",
            ),
        ]
        repo = MockEntryRepository(entries=entries)
        goal = DailyGoal(target_calories=2000)

        summary = await get_daily_summary("2024-01-15", repo, goal)

        assert summary.total_calories == 800
        assert summary.remaining_calories == 1200
        assert summary.status == GoalStatus.WITHIN_GOAL
        assert len(summary.entries) == 2

    async def test_no_entries(self):
        """Date with no entries returns zero totals and WITHIN_GOAL status."""
        repo = MockEntryRepository(entries=[])
        goal = DailyGoal(target_calories=2000)

        summary = await get_daily_summary("2024-01-15", repo, goal)

        assert summary.total_calories == 0
        assert summary.remaining_calories == 2000
        assert summary.status == GoalStatus.WITHIN_GOAL
        assert len(summary.entries) == 0

    async def test_total_equals_sum_of_entry_calories(self):
        """total_calories always equals the sum of individual entry calories."""
        entries = [
            FoodEntry(
                entry_id="1",
                food_name="Apple",
                calories=95,
                confidence=0.92,
                timestamp="2024-01-15T09:00:00Z",
                date="2024-01-15",
            ),
            FoodEntry(
                entry_id="2",
                food_name="Pasta",
                calories=680,
                confidence=0.78,
                timestamp="2024-01-15T13:00:00Z",
                date="2024-01-15",
            ),
            FoodEntry(
                entry_id="3",
                food_name="Steak",
                calories=750,
                confidence=0.88,
                timestamp="2024-01-15T19:00:00Z",
                date="2024-01-15",
            ),
        ]
        repo = MockEntryRepository(entries=entries)
        goal = DailyGoal(target_calories=2000)

        summary = await get_daily_summary("2024-01-15", repo, goal)

        expected_total = sum(e.calories for e in entries)
        assert summary.total_calories == expected_total
        assert summary.remaining_calories == max(0, 2000 - expected_total)


# ---------------------------------------------------------------------------
# complete_onboarding tests
# ---------------------------------------------------------------------------


class TestCompleteOnboarding:
    """Tests for complete_onboarding use case."""

    async def test_happy_path(self):
        """Valid inputs create profile, weight record, and calculate TDEE."""
        repo = MockUserProfileRepository()

        result = await complete_onboarding(
            weight_kg=75.0,
            height_cm=175.0,
            age=30,
            sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE,
            profile_repository=repo,
        )

        # TDEE was calculated correctly
        expected_tdee = calculate_tdee(75.0, 175.0, 30, Sex.MALE, ActivityLevel.MODERATE)
        assert result.tdee == expected_tdee

        # Suggested goal uses default deficit
        expected_goal = suggest_calorie_goal(expected_tdee)
        assert result.suggested_goal == expected_goal

        # Profile was saved
        assert len(repo.saved_profiles) == 1
        saved_profile = repo.saved_profiles[0]
        assert saved_profile.weight_kg == 75.0
        assert saved_profile.height_cm == 175.0
        assert saved_profile.age == 30
        assert saved_profile.sex == Sex.MALE
        assert saved_profile.activity_level == ActivityLevel.MODERATE
        assert saved_profile.tdee == expected_tdee
        assert saved_profile.daily_calorie_goal == expected_goal

        # Weight record was saved
        assert len(repo.saved_weight_records) == 1
        assert repo.saved_weight_records[0].weight_kg == 75.0

    async def test_weight_below_minimum_raises_value_error(self):
        """Weight below 30 kg raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Weight must be between 30 and 300 kg"):
            await complete_onboarding(
                weight_kg=29.9,
                height_cm=175.0,
                age=30,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )

    async def test_weight_above_maximum_raises_value_error(self):
        """Weight above 300 kg raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Weight must be between 30 and 300 kg"):
            await complete_onboarding(
                weight_kg=300.1,
                height_cm=175.0,
                age=30,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )

    async def test_height_below_minimum_raises_value_error(self):
        """Height below 100 cm raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Height must be between 100 and 250 cm"):
            await complete_onboarding(
                weight_kg=75.0,
                height_cm=99.9,
                age=30,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )

    async def test_height_above_maximum_raises_value_error(self):
        """Height above 250 cm raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Height must be between 100 and 250 cm"):
            await complete_onboarding(
                weight_kg=75.0,
                height_cm=250.1,
                age=30,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )

    async def test_age_below_minimum_raises_value_error(self):
        """Age below 13 raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Age must be between 13 and 120"):
            await complete_onboarding(
                weight_kg=75.0,
                height_cm=175.0,
                age=12,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )

    async def test_age_above_maximum_raises_value_error(self):
        """Age above 120 raises ValueError."""
        repo = MockUserProfileRepository()

        with pytest.raises(ValueError, match="Age must be between 13 and 120"):
            await complete_onboarding(
                weight_kg=75.0,
                height_cm=175.0,
                age=121,
                sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE,
                profile_repository=repo,
            )


# ---------------------------------------------------------------------------
# update_weight tests
# ---------------------------------------------------------------------------


class TestUpdateWeight:
    """Tests for update_weight use case."""

    async def test_happy_path(self):
        """Existing profile is updated with new weight and recalculated TDEE."""
        existing_profile = UserProfile(
            weight_kg=80.0,
            height_cm=180.0,
            age=28,
            sex=Sex.MALE,
            activity_level=ActivityLevel.ACTIVE,
            daily_calorie_goal=2400,
            tdee=2800,
        )
        repo = MockUserProfileRepository(profile=existing_profile)

        result = await update_weight(new_weight_kg=78.0, profile_repository=repo)

        # TDEE recalculated with new weight
        expected_tdee = calculate_tdee(
            78.0, 180.0, 28, Sex.MALE, ActivityLevel.ACTIVE
        )
        assert result.new_tdee == expected_tdee
        assert result.suggested_goal == suggest_calorie_goal(expected_tdee)

        # Profile was saved with new weight
        assert len(repo.saved_profiles) == 1
        assert repo.saved_profiles[0].weight_kg == 78.0

        # Weight record was saved
        assert len(repo.saved_weight_records) == 1
        assert repo.saved_weight_records[0].weight_kg == 78.0

    async def test_no_profile_raises_value_error(self):
        """Attempting to update weight without an existing profile raises ValueError."""
        repo = MockUserProfileRepository(profile=None)

        with pytest.raises(ValueError, match="No profile exists"):
            await update_weight(new_weight_kg=75.0, profile_repository=repo)

    async def test_preserves_non_weight_fields(self):
        """Update weight preserves height, age, sex, and activity_level."""
        existing_profile = UserProfile(
            weight_kg=70.0,
            height_cm=165.0,
            age=35,
            sex=Sex.FEMALE,
            activity_level=ActivityLevel.LIGHT,
            daily_calorie_goal=1800,
            tdee=2000,
        )
        repo = MockUserProfileRepository(profile=existing_profile)

        result = await update_weight(new_weight_kg=68.0, profile_repository=repo)

        updated = result.updated_profile
        assert updated.weight_kg == 68.0
        assert updated.height_cm == 165.0
        assert updated.age == 35
        assert updated.sex == Sex.FEMALE
        assert updated.activity_level == ActivityLevel.LIGHT
