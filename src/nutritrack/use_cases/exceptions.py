class FoodNotRecognizedError(Exception):
    """Raised when the AI cannot identify food in the image."""

    pass


class InvalidImageError(Exception):
    """Raised when the image data is invalid (empty, too large, etc.)."""

    pass


class AIServiceUnavailableError(Exception):
    """Raised when the AI service is unreachable or returns errors."""

    pass


class PersistenceError(Exception):
    """Raised when a database operation fails."""

    pass
