"""Web novel module exceptions."""
from fastapi import HTTPException
from typing import Optional


class WebNovelException(HTTPException):
    """Base exception for web novel module."""
    def __init__(self, detail: str, error_code: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail={"detail": detail, "error_code": error_code})


class NovelNotFoundError(WebNovelException):
    def __init__(self, novel_id: Optional[str] = None):
        detail = f"Novel not found: {novel_id}" if novel_id else "Novel not found"
        super().__init__(detail=detail, error_code="NOVEL_NOT_FOUND", status_code=404)


class NovelAlreadyExistsError(WebNovelException):
    def __init__(self, novel_id: str):
        super().__init__(
            detail=f"Novel already exists: {novel_id}",
            error_code="NOVEL_ALREADY_EXISTS",
            status_code=409
        )


class InvalidUrlError(WebNovelException):
    def __init__(self, detail: str = "Invalid Syosetsu URL"):
        super().__init__(detail=detail, error_code="INVALID_URL", status_code=400)


class ProviderError(WebNovelException):
    def __init__(self, detail: str = "Provider error"):
        super().__init__(detail=detail, error_code="PROVIDER_ERROR", status_code=502)


class SyncError(WebNovelException):
    def __init__(self, detail: str = "Sync failed"):
        super().__init__(detail=detail, error_code="SYNC_ERROR", status_code=500)