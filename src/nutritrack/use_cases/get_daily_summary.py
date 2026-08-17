from nutritrack.domain.models import DailyGoal, DailySummary

from .ports import EntryRepository


async def get_daily_summary(
    target_date: str,
    entry_repository: EntryRepository,
    daily_goal: DailyGoal,
) -> DailySummary:
    """
    Retrieve and compute the daily calorie summary for a given date.

    Queries all entries for the target date, sums calories,
    evaluates goal status, and returns the summary.
    """
    entries = await entry_repository.get_entries_by_date(target_date)
    total_calories = sum(e.calories for e in entries)
    remaining = max(0, daily_goal.target_calories - total_calories)
    status = daily_goal.evaluate(total_calories)

    return DailySummary(
        date=target_date,
        entries=entries,
        total_calories=total_calories,
        goal=daily_goal,
        status=status,
        remaining_calories=remaining,
    )
