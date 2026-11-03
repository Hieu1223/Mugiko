"""Manga module base exceptions."""
from fastapi import HTTPException, status


class MangaError(HTTPException):
    """Base exception for manga module."""
    def __init__(self, detail: str = "Manga error", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, error_code: str = "MANGA_ERROR"):
        super().__init__(status_code=status_code, detail={"error": {"code": error_code, "message": detail}})


class ProviderNotFoundError(MangaError):
    """Provider not found."""
    def __init__(self):
        super().__init__(detail="Manga provider not found", status_code=status.HTTP_404_NOT_FOUND, error_code="PROVIDER_NOT_FOUND")


class ProviderValidationError(MangaError):
    """Provider validation failed."""
    def __init__(self, detail: str = "Provider validation failed"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST, error_code="PROVIDER_VALIDATION_FAILED")


class SubscriptionNotFoundError(MangaError):
    """Subscription not found."""
    def __init__(self):
        super().__init__(detail="Subscription not found", status_code=status.HTTP_404_NOT_FOUND, error_code="SUBSCRIPTION_NOT_FOUND")


class HistoryNotFoundError(MangaError):
    """History entry not found."""
    def __init__(self):
        super().__init__(detail="Reading history not found", status_code=status.HTTP_404_NOT_FOUND, error_code="HISTORY_NOT_FOUND")


class ForbiddenError(MangaError):
    """Forbidden access."""
    def __init__(self, detail: str = "Access forbidden"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN, error_code="FORBIDDEN")


class InvalidProviderUrlError(MangaError):
    """Invalid provider URL."""
    def __init__(self, detail: str = "Invalid provider URL"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST, error_code="INVALID_PROVIDER_URL")


class BuiltinProviderError(MangaError):
    """Built-in provider error."""
    def __init__(self, detail: str = "Built-in provider error"):
        super().__init__(detail=detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, error_code="BUILTIN_PROVIDER_ERROR")


class TagFilterError(MangaError):
    """Tag filter expression error."""
    def __init__(self, detail: str = "Invalid tag filter expression"):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST, error_code="TAG_FILTER_ERROR")


class AlreadySubscribedError(MangaError):
    """User is already subscribed to this provider."""
    def __init__(self):
        super().__init__(detail="Already subscribed to this provider", status_code=status.HTTP_409_CONFLICT, error_code="ALREADY_SUBSCRIBED")