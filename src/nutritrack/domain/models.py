from dataclasses import dataclass
from enum import Enum


class GoalStatus(Enum):
    WITHIN_GOAL = "within_goal"
    EXCEEDED = "exceeded"


class Sex(Enum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


ACTIVITY_MULTIPLIERS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


@dataclass(frozen=True)
class UserProfile:
    weight_kg: float
    height_cm: float
    age: int
    sex: Sex
    activity_level: ActivityLevel
    daily_calorie_goal: int
    tdee: int


@dataclass(frozen=True)
class WeightRecord:
    date: str  # ISO format YYYY-MM-DD
    weight_kg: float


@dataclass(frozen=True)
class FoodEntry:
    entry_id: str
    food_name: str
    calories: int
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    confidence: float = 0.0
    timestamp: str = ""
    date: str = ""


@dataclass(frozen=True)
class DailyGoal:
    target_calories: int

    def evaluate(self, total_calories: int) -> GoalStatus:
        if total_calories <= self.target_calories:
            return GoalStatus.WITHIN_GOAL
        return GoalStatus.EXCEEDED


@dataclass(frozen=True)
class DailySummary:
    date: str
    entries: list[FoodEntry]
    total_calories: int
    goal: DailyGoal
    status: GoalStatus
    remaining_calories: int


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """
    Mifflin-St Jeor BMR formula.

    Male:   BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + 5
    Female: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) - 161
    """
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    if sex == Sex.MALE:
        return base + 5
    return base - 161


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    activity_level: ActivityLevel,
) -> int:
    """
    TDEE = BMR × Activity Multiplier.
    Returns rounded integer.
    """
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
    multiplier = ACTIVITY_MULTIPLIERS[activity_level]
    return round(bmr * multiplier)


def suggest_calorie_goal(tdee: int, deficit: int = 400) -> int:
    """
    Suggest daily calorie goal with a deficit.
    Default deficit is 400 kcal (midpoint of 300-500 range).

    PRECONDITION: 300 <= deficit <= 500
    POSTCONDITION: result = max(tdee - deficit, 1200) (safety floor)
    """
    goal = tdee - deficit
    return max(goal, 1200)
