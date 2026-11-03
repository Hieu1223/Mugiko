"""Provider exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException


class ProviderNotFoundError(UserManagementException):
    def __init__(self, detail: str = "Provider not found"):
        super().__init__(detail=detail, status_code=404)


class ProviderSyncError(UserManagementException):
    def __init__(self, detail: str = "Provider sync failed"):
        super().__init__(detail=detail, status_code=500)


class InvalidProviderConfigError(UserManagementException):
    def __init__(self, detail: str = "Invalid provider configuration"):
        super().__init__(detail=detail, status_code=400)