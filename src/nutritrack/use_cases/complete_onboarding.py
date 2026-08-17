from datetime import datetime, timezone

from nutritrack.domain.models import (
    ActivityLevel,
    Sex,
    UserProfile,
    WeightRecord,
    calculate_tdee,
    suggest_calorie_goal,
)

from .ports import UserProfileRepository
from .results import OnboardingResult


async def complete_onboarding(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    activity_level: ActivityLevel,
    profile_repository: UserProfileRepository,
) -> OnboardingResult:
    """
    Complete user onboarding by calculating TDEE and creating a profile.

    Validates inputs, calculates TDEE using the Mifflin-St Jeor formula,
    suggests a calorie goal, persists the profile and initial weight record.
    """
    # Validate inputs
    if not (30.0 <= weight_kg <= 300.0):
        raise ValueError("Weight must be between 30 and 300 kg")
    if not (100.0 <= height_cm <= 250.0):
        raise ValueError("Height must be between 100 and 250 cm")
    if not (13 <= age <= 120):
        raise ValueError("Age must be between 13 and 120")

    # Calculate TDEE and suggest goal
    tdee = calculate_tdee(weight_kg, height_cm, age, sex, activity_level)
    suggested_goal = suggest_calorie_goal(tdee)

    # Create profile
    profile = UserProfile(
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        sex=sex,
        activity_level=activity_level,
        daily_calorie_goal=suggested_goal,
        tdee=tdee,
    )

    # Persist profile
    await profile_repository.save_profile(profile)

    # Save initial weight record
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    weight_record = WeightRecord(date=today, weight_kg=weight_kg)
    await profile_repository.save_weight_record(weight_record)

    return OnboardingResult(
        profile=profile,
        tdee=tdee,
        suggested_goal=suggested_goal,
    )
