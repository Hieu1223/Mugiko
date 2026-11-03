"""Validation exceptions."""
from .base import UserManagementException


class InvalidRoleError(UserManagementException):
    """Invalid role specified."""

    def __init__(self, detail: str = "Invalid role"):
        super().__init__(detail=detail, status_code=400)


class ValidationError(UserManagementException):
    """Validation error."""

    def __init__(self, detail: str = "Validation failed"):
        super().__init__(detail=detail, status_code=422)