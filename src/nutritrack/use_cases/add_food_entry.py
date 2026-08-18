from datetime import datetime, timezone, timedelta
from uuid import uuid4

from nutritrack.domain.models import DailyGoal, DailySummary, FoodEntry

from .exceptions import InvalidImageError
from .ports import EntryRepository, ImageAnalyzer
from .results import AddEntryResult

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


async def add_food_entry(
    image_data: bytes,
    image_analyzer: ImageAnalyzer,
    entry_repository: EntryRepository,
    daily_goal: DailyGoal,
    local_date: str = "",
) -> AddEntryResult:
    """
    Process a food image and create a calorie entry.

    Validates image data, calls the AI analyzer, persists the entry,
    and returns the entry with an updated daily summary.
    """
    # Step 1: Validate input
    if not image_data:
        raise InvalidImageError("Image data must not be empty")
    if len(image_data) > MAX_IMAGE_SIZE:
        raise InvalidImageError("Image exceeds 20MB limit")

    # Step 2: Analyze image with AI
    analysis = await image_analyzer.analyze_food_image(image_data)

    # Step 3: Generate unique entry ID and timestamp
    entry_id = str(uuid4())
    now = datetime.now(timezone.utc)
    today = local_date if local_date else now.strftime("%Y-%m-%d")
    timestamp = now.isoformat()

    # Step 4: Create domain entity
    entry = FoodEntry(
        entry_id=entry_id,
        food_name=analysis.food_name,
        calories=analysis.estimated_calories,
        protein_g=analysis.protein_g,
        carbs_g=analysis.carbs_g,
        fat_g=analysis.fat_g,
        confidence=analysis.confidence,
        timestamp=timestamp,
        date=today,
    )

    # Step 5: Persist entry
    await entry_repository.save_entry(entry)

    # Step 6: Calculate daily summary
    all_entries = await entry_repository.get_entries_by_date(today)
    total_calories = sum(e.calories for e in all_entries)
    status = daily_goal.evaluate(total_calories)
    remaining = max(0, daily_goal.target_calories - total_calories)

    summary = DailySummary(
        date=today,
        entries=all_entries,
        total_calories=total_calories,
        goal=daily_goal,
        status=status,
        remaining_calories=remaining,
    )

    return AddEntryResult(entry=entry, daily_summary=summary)
