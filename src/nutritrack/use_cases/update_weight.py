from datetime import datetime, timezone

from nutritrack.domain.models import (
    UserProfile,
    WeightRecord,
    calculate_tdee,
    suggest_calorie_goal,
)

from .ports import UserProfileRepository
from .results import WeightUpdateResult


async def update_weight(
    new_weight_kg: float,
    profile_repository: UserProfileRepository,
) -> WeightUpdateResult:
    """
    Update user weight, recalculate TDEE, and suggest a new goal.

    Validates the new weight, retrieves the existing profile,
    recalculates TDEE with the updated weight, persists the
    updated profile and a new weight record.
    """
    # Validate weight
    if not (30.0 <= new_weight_kg <= 300.0):
        raise ValueError("Weight must be between 30 and 300 kg")

    # Get existing profile
    profile = await profile_repository.get_profile()
    if profile is None:
        raise ValueError("No profile exists. Complete onboarding first.")

    # Recalculate TDEE with new weight
    new_tdee = calculate_tdee(
        new_weight_kg,
        profile.height_cm,
        profile.age,
        profile.sex,
        profile.activity_level,
    )
    new_suggested_goal = suggest_calorie_goal(new_tdee)

    # Create updated profile (preserves all non-weight fields)
    updated_profile = UserProfile(
        weight_kg=new_weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        activity_level=profile.activity_level,
        daily_calorie_goal=new_suggested_goal,
        tdee=new_tdee,
    )

    # Persist updated profile
    await profile_repository.save_profile(updated_profile)

    # Save weight record
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    weight_record = WeightRecord(date=today, weight_kg=new_weight_kg)
    await profile_repository.save_weight_record(weight_record)

    # Get weight history
    weight_history = await profile_repository.get_weight_history()

    return WeightUpdateResult(
        updated_profile=updated_profile,
        new_tdee=new_tdee,
        suggested_goal=new_suggested_goal,
        weight_history=weight_history,
    )
