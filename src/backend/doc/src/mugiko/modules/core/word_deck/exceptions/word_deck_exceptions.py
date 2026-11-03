"""Exceptions for word deck module."""
from typing import Optional
from fastapi import HTTPException, status


class WordDeckException(HTTPException):
    """Base exception for word deck module."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: Optional[dict] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or self.__class__.__name__


class DeckNotFoundError(WordDeckException):
    """Raised when a deck is not found."""
    def __init__(self, deck_id: str = None):
        detail = f"Deck {deck_id} not found" if deck_id else "Deck not found"
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND, error_code="DECK_NOT_FOUND")


class DeckWordNotFoundError(WordDeckException):
    """Raised when a deck word is not found."""
    def __init__(self, word_id: str = None):
        detail = f"Word {word_id} not found" if word_id else "Word not found"
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND, error_code="WORD_NOT_FOUND")


class DeckAccessDeniedError(WordDeckException):
    """Raised when user tries to access another user's deck."""
    def __init__(self):
        super().__init__(detail="Access denied to this deck", status_code=status.HTTP_403_FORBIDDEN, error_code="DECK_ACCESS_DENIED")


class DeckValidationError(WordDeckException):
    """Raised when deck validation fails."""
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST, error_code="DECK_VALIDATION_ERROR")