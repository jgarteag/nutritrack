from dataclasses import dataclass

from nutritrack.domain.models import DailySummary, FoodEntry, UserProfile, WeightRecord


@dataclass(frozen=True)
class FoodAnalysisResult:
    food_name: str
    estimated_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: float


@dataclass(frozen=True)
class OnboardingResult:
    profile: UserProfile
    tdee: int
    suggested_goal: int


@dataclass(frozen=True)
class WeightUpdateResult:
    updated_profile: UserProfile
    new_tdee: int
    suggested_goal: int
    weight_history: list[WeightRecord]


@dataclass(frozen=True)
class AddEntryResult:
    entry: FoodEntry
    daily_summary: DailySummary
