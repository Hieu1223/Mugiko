"""Conflict exceptions."""
from .base import UserManagementException


class UserAlreadyExistsError(UserManagementException):
    """User already exists (conflict)."""

    def __init__(self, detail: str = "User already exists"):
        super().__init__(detail=detail, status_code=409)