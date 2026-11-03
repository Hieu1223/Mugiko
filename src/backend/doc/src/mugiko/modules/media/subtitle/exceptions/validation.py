"""Validation exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException


class InvalidVideoURLError(UserManagementException):
    def __init__(self, detail: str = "Invalid YouTube URL"):
        super().__init__(detail=detail, status_code=400)


class ValidationError(UserManagementException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail=detail, status_code=422)