from typing import Optional, Protocol

from nutritrack.domain.models import FoodEntry, UserProfile, WeightRecord

from .results import FoodAnalysisResult


class ImageAnalyzer(Protocol):
    """Port: AI service for food recognition."""

    async def analyze_food_image(self, image_data: bytes) -> FoodAnalysisResult: ...


class EntryRepository(Protocol):
    """Port: Persistence for food entries."""

    async def save_entry(self, entry: FoodEntry) -> None: ...

    async def get_entries_by_date(self, date: str) -> list[FoodEntry]: ...


class UserProfileRepository(Protocol):
    """Port: Persistence for user profile and weight history."""

    async def get_profile(self) -> Optional[UserProfile]: ...

    async def save_profile(self, profile: UserProfile) -> None: ...

    async def save_weight_record(self, record: WeightRecord) -> None: ...

    async def get_weight_history(self, limit: int = 30) -> list[WeightRecord]: ...
