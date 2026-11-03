"""Authentication-related exceptions."""
from .base import UserManagementException
from typing import Optional


class AuthenticationError(UserManagementException):
    """Authentication failed or missing."""

    def __init__(self, detail: str = "Authentication required", headers: Optional[dict] = None):
        super().__init__(detail=detail, status_code=401, headers=headers)


class InvalidTokenError(AuthenticationError):
    """Invalid token format or content."""

    def __init__(self, detail: str = "Invalid token", headers: Optional[dict] = None):
        super().__init__(detail=detail, headers=headers)


class FirebaseTokenError(InvalidTokenError):
    """Invalid or expired Firebase token."""

    def __init__(self, detail: str = "Invalid Firebase token"):
        super().__init__(detail=detail)


class AdminTokenError(InvalidTokenError):
    """Invalid admin token."""

    def __init__(self, detail: str = "Invalid admin token"):
        super().__init__(detail=detail)