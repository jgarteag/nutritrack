"""
Domain layer unit tests for NutriTrack.

Validates: Requirements 9 (Clean Architecture & TDD), 2 (Onboarding & TDEE Calculation)
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nutritrack.domain.models import (
    ACTIVITY_MULTIPLIERS,
    ActivityLevel,
    DailyGoal,
    GoalStatus,
    Sex,
    calculate_bmr,
    calculate_tdee,
    suggest_calorie_goal,
)


# ---------------------------------------------------------------------------
# Strategies for property-based tests
# ---------------------------------------------------------------------------

weight_st = st.floats(min_value=30.0, max_value=300.0, allow_nan=False, allow_infinity=False)
height_st = st.floats(min_value=100.0, max_value=250.0, allow_nan=False, allow_infinity=False)
age_st = st.integers(min_value=13, max_value=120)
sex_st = st.sampled_from([Sex.MALE, Sex.FEMALE])
activity_st = st.sampled_from(list(ActivityLevel))


# ===========================================================================
# BMR Tests
# ===========================================================================


class TestCalculateBMR:
    """Tests for calculate_bmr() using Mifflin-St Jeor formula."""

    def test_male_known_value(self):
        """Male BMR = (10 × 80) + (6.25 × 175) - (5 × 30) + 5 = 800 + 1093.75 - 150 + 5 = 1748.75"""
        result = calculate_bmr(weight_kg=80.0, height_cm=175.0, age=30, sex=Sex.MALE)
        assert result == pytest.approx(1748.75)

    def test_female_known_value(self):
        """Female BMR = (10 × 60) + (6.25 × 165) - (5 × 25) - 161 = 600 + 1031.25 - 125 - 161 = 1345.25"""
        result = calculate_bmr(weight_kg=60.0, height_cm=165.0, age=25, sex=Sex.FEMALE)
        assert result == pytest.approx(1345.25)

    def test_male_vs_female_difference(self):
        """Male BMR should be exactly 166 higher than female BMR for same inputs (5 - (-161) = 166)."""
        male_bmr = calculate_bmr(weight_kg=70.0, height_cm=170.0, age=28, sex=Sex.MALE)
        female_bmr = calculate_bmr(weight_kg=70.0, height_cm=170.0, age=28, sex=Sex.FEMALE)
        assert male_bmr - female_bmr == pytest.approx(166.0)

    def test_formula_components_male(self):
        """Verify each component of the male formula."""
        weight, height, age = 75.0, 180.0, 35
        expected = (10 * weight) + (6.25 * height) - (5 * age) + 5
        result = calculate_bmr(weight, height, age, Sex.MALE)
        assert result == pytest.approx(expected)

    def test_formula_components_female(self):
        """Verify each component of the female formula."""
        weight, height, age = 55.0, 160.0, 22
        expected = (10 * weight) + (6.25 * height) - (5 * age) - 161
        result = calculate_bmr(weight, height, age, Sex.FEMALE)
        assert result == pytest.approx(expected)


# ===========================================================================
# TDEE Tests
# ===========================================================================


class TestCalculateTDEE:
    """Tests for calculate_tdee() verifying multipliers applied correctly."""

    def test_sedentary_multiplier(self):
        """TDEE with sedentary level uses multiplier 1.2."""
        bmr = calculate_bmr(80.0, 175.0, 30, Sex.MALE)
        expected = round(bmr * 1.2)
        result = calculate_tdee(80.0, 175.0, 30, Sex.MALE, ActivityLevel.SEDENTARY)
        assert result == expected

    def test_light_multiplier(self):
        """TDEE with light level uses multiplier 1.375."""
        bmr = calculate_bmr(80.0, 175.0, 30, Sex.MALE)
        expected = round(bmr * 1.375)
        result = calculate_tdee(80.0, 175.0, 30, Sex.MALE, ActivityLevel.LIGHT)
        assert result == expected

    def test_moderate_multiplier(self):
        """TDEE with moderate level uses multiplier 1.55."""
        bmr = calculate_bmr(80.0, 175.0, 30, Sex.MALE)
        expected = round(bmr * 1.55)
        result = calculate_tdee(80.0, 175.0, 30, Sex.MALE, ActivityLevel.MODERATE)
        assert result == expected

    def test_active_multiplier(self):
        """TDEE with active level uses multiplier 1.725."""
        bmr = calculate_bmr(80.0, 175.0, 30, Sex.MALE)
        expected = round(bmr * 1.725)
        result = calculate_tdee(80.0, 175.0, 30, Sex.MALE, ActivityLevel.ACTIVE)
        assert result == expected

    def test_very_active_multiplier(self):
        """TDEE with very_active level uses multiplier 1.9."""
        bmr = calculate_bmr(80.0, 175.0, 30, Sex.MALE)
        expected = round(bmr * 1.9)
        result = calculate_tdee(80.0, 175.0, 30, Sex.MALE, ActivityLevel.VERY_ACTIVE)
        assert result == expected

    def test_all_multipliers_match_constant(self):
        """Verify all activity multipliers are used correctly."""
        for level, multiplier in ACTIVITY_MULTIPLIERS.items():
            bmr = calculate_bmr(70.0, 170.0, 25, Sex.FEMALE)
            expected = round(bmr * multiplier)
            result = calculate_tdee(70.0, 170.0, 25, Sex.FEMALE, level)
            assert result == expected, f"Failed for activity level {level}"

    def test_returns_integer(self):
        """TDEE should always return a rounded integer."""
        result = calculate_tdee(72.5, 168.3, 29, Sex.MALE, ActivityLevel.MODERATE)
        assert isinstance(result, int)


# ===========================================================================
# Monotonicity Property Tests
# ===========================================================================


class TestTDEEMonotonicity:
    """
    Property tests verifying monotonicity of TDEE.

    **Validates: Requirements 2**
    """

    @given(
        w1=st.floats(min_value=30.0, max_value=149.0, allow_nan=False, allow_infinity=False),
        delta=st.floats(min_value=1.0, max_value=150.0, allow_nan=False, allow_infinity=False),
        height=height_st,
        age=age_st,
        sex=sex_st,
        activity=activity_st,
    )
    def test_higher_weight_higher_tdee(self, w1, delta, height, age, sex, activity):
        """Higher weight → higher TDEE (all other inputs equal)."""
        w2 = w1 + delta
        tdee1 = calculate_tdee(w1, height, age, sex, activity)
        tdee2 = calculate_tdee(w2, height, age, sex, activity)
        assert tdee2 >= tdee1

    @given(
        h1=st.floats(min_value=100.0, max_value=174.0, allow_nan=False, allow_infinity=False),
        delta=st.floats(min_value=1.0, max_value=75.0, allow_nan=False, allow_infinity=False),
        weight=weight_st,
        age=age_st,
        sex=sex_st,
        activity=activity_st,
    )
    def test_higher_height_higher_tdee(self, h1, delta, weight, age, sex, activity):
        """Higher height → higher TDEE (all other inputs equal)."""
        h2 = h1 + delta
        tdee1 = calculate_tdee(weight, h1, age, sex, activity)
        tdee2 = calculate_tdee(weight, h2, age, sex, activity)
        assert tdee2 >= tdee1

    @given(
        weight=weight_st,
        height=height_st,
        age=age_st,
        sex=sex_st,
    )
    def test_higher_activity_level_higher_tdee(self, weight, height, age, sex):
        """Higher activity level → higher TDEE (all other inputs equal)."""
        ordered_levels = [
            ActivityLevel.SEDENTARY,
            ActivityLevel.LIGHT,
            ActivityLevel.MODERATE,
            ActivityLevel.ACTIVE,
            ActivityLevel.VERY_ACTIVE,
        ]
        tdees = [calculate_tdee(weight, height, age, sex, level) for level in ordered_levels]
        for i in range(len(tdees) - 1):
            assert tdees[i + 1] >= tdees[i], (
                f"TDEE did not increase from {ordered_levels[i]} to {ordered_levels[i+1]}"
            )


# ===========================================================================
# Determinism and Male > Female Property Tests
# ===========================================================================


class TestTDEEProperties:
    """
    Property tests for determinism and sex-based TDEE difference.

    **Validates: Requirements 2**
    """

    @given(
        weight=weight_st,
        height=height_st,
        age=age_st,
        sex=sex_st,
        activity=activity_st,
    )
    def test_determinism(self, weight, height, age, sex, activity):
        """For same inputs, calculate_tdee always returns same output (pure function)."""
        result1 = calculate_tdee(weight, height, age, sex, activity)
        result2 = calculate_tdee(weight, height, age, sex, activity)
        assert result1 == result2

    @given(
        weight=weight_st,
        height=height_st,
        age=age_st,
        activity=activity_st,
    )
    def test_male_tdee_greater_than_female(self, weight, height, age, activity):
        """Male TDEE > Female TDEE for same inputs. BMR difference is 166, multiplied by activity."""
        male_tdee = calculate_tdee(weight, height, age, Sex.MALE, activity)
        female_tdee = calculate_tdee(weight, height, age, Sex.FEMALE, activity)
        assert male_tdee >= female_tdee

    @given(
        weight=weight_st,
        height=height_st,
        age=age_st,
        activity=activity_st,
    )
    def test_male_female_bmr_difference_is_166(self, weight, height, age, activity):
        """The BMR difference between male and female is always exactly 166."""
        male_bmr = calculate_bmr(weight, height, age, Sex.MALE)
        female_bmr = calculate_bmr(weight, height, age, Sex.FEMALE)
        assert male_bmr - female_bmr == pytest.approx(166.0)


# ===========================================================================
# suggest_calorie_goal Tests
# ===========================================================================


class TestSuggestCalorieGoal:
    """Tests for suggest_calorie_goal() with deficit and safety floor."""

    def test_normal_deficit(self):
        """Normal case: TDEE 2200 with 400 deficit = 1800."""
        result = suggest_calorie_goal(tdee=2200, deficit=400)
        assert result == 1800

    def test_default_deficit_is_400(self):
        """Default deficit parameter is 400."""
        result = suggest_calorie_goal(tdee=2000)
        assert result == 1600

    def test_safety_floor_at_1200(self):
        """Goal should never go below 1200 kcal (safety floor)."""
        result = suggest_calorie_goal(tdee=1400, deficit=500)
        assert result == 1200

    def test_safety_floor_exact_boundary(self):
        """When tdee - deficit == 1200, result is exactly 1200."""
        result = suggest_calorie_goal(tdee=1700, deficit=500)
        assert result == 1200

    def test_safety_floor_just_above(self):
        """When tdee - deficit == 1201, result is 1201 (just above floor)."""
        result = suggest_calorie_goal(tdee=1501, deficit=300)
        assert result == 1201

    def test_deficit_boundary_300(self):
        """Minimum deficit of 300."""
        result = suggest_calorie_goal(tdee=2500, deficit=300)
        assert result == 2200

    def test_deficit_boundary_500(self):
        """Maximum deficit of 500."""
        result = suggest_calorie_goal(tdee=2500, deficit=500)
        assert result == 2000

    def test_very_low_tdee_hits_floor(self):
        """Very low TDEE triggers safety floor."""
        result = suggest_calorie_goal(tdee=1300, deficit=300)
        assert result == 1200

    def test_result_equals_max_formula(self):
        """Result always equals max(tdee - deficit, 1200)."""
        test_cases = [
            (2500, 400),
            (1800, 300),
            (1500, 500),
            (1200, 300),
        ]
        for tdee, deficit in test_cases:
            expected = max(tdee - deficit, 1200)
            result = suggest_calorie_goal(tdee, deficit)
            assert result == expected, f"Failed for tdee={tdee}, deficit={deficit}"


# ===========================================================================
# DailyGoal.evaluate Tests
# ===========================================================================


class TestDailyGoalEvaluate:
    """Tests for DailyGoal.evaluate() method."""

    def test_total_less_than_goal(self):
        """When total_calories < target_calories → WITHIN_GOAL."""
        goal = DailyGoal(target_calories=2000)
        assert goal.evaluate(total_calories=1500) == GoalStatus.WITHIN_GOAL

    def test_total_equals_goal(self):
        """When total_calories == target_calories → WITHIN_GOAL."""
        goal = DailyGoal(target_calories=2000)
        assert goal.evaluate(total_calories=2000) == GoalStatus.WITHIN_GOAL

    def test_total_exceeds_goal(self):
        """When total_calories > target_calories → EXCEEDED."""
        goal = DailyGoal(target_calories=2000)
        assert goal.evaluate(total_calories=2001) == GoalStatus.EXCEEDED

    def test_zero_calories_within_goal(self):
        """Zero calories consumed is always within goal."""
        goal = DailyGoal(target_calories=1500)
        assert goal.evaluate(total_calories=0) == GoalStatus.WITHIN_GOAL

    def test_one_over_exceeds(self):
        """Even 1 calorie over the goal means EXCEEDED."""
        goal = DailyGoal(target_calories=1800)
        assert goal.evaluate(total_calories=1801) == GoalStatus.EXCEEDED
