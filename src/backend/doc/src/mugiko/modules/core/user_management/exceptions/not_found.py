"""Not found exceptions."""
from .base import UserManagementException


class UserNotFoundError(UserManagementException):
    """User not found."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail, status_code=404)


class ProfileNotFoundError(UserManagementException):
    """User profile not found."""

    def __init__(self, detail: str = "Profile not found"):
        super().__init__(detail=detail, status_code=404)