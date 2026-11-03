"""Subtitle exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException


class SubtitleNotFoundError(UserManagementException):
    def __init__(self, detail: str = "Subtitle not found"):
        super().__init__(detail=detail, status_code=404)


class SubtitleGenerationError(UserManagementException):
    def __init__(self, detail: str = "Subtitle generation failed"):
        super().__init__(detail=detail, status_code=500)


class ServiceNotFoundError(UserManagementException):
    def __init__(self, detail: str = "Service not found"):
        super().__init__(detail=detail, status_code=404)