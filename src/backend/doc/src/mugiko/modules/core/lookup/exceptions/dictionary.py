"""Dictionary exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException


class DictionaryNotFoundError(UserManagementException):
    """Raised when dictionary file is not found."""

    def __init__(self, detail: str = "Dictionary file not found"):
        super().__init__(detail=detail, status_code=500)


class DictionaryCorruptedError(UserManagementException):
    """Raised when dictionary file is corrupted or invalid."""

    def __init__(self, detail: str = "Dictionary file is corrupted"):
        super().__init__(detail=detail, status_code=500)


class WordNotFoundError(UserManagementException):
    """Raised when word is not found in dictionary."""

    def __init__(self, detail: str = "Word not found"):
        super().__init__(detail=detail, status_code=404)


class KanjiNotFoundError(UserManagementException):
    """Raised when kanji is not found in dictionary."""

    def __init__(self, detail: str = "Kanji not found"):
        super().__init__(detail=detail, status_code=404)


class InvalidKanjiError(UserManagementException):
    """Raised when input is not a valid single kanji character."""

    def __init__(self, detail: str = "Input must be a single kanji character"):
        super().__init__(detail=detail, status_code=400)