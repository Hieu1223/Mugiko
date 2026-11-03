"""Authorization-related exceptions."""
from .base import UserManagementException


class AuthorizationError(UserManagementException):
    """Authorization failed - insufficient permissions."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail=detail, status_code=403)


class AnonymousUserError(AuthorizationError):
    """Anonymous users cannot perform this action."""

    def __init__(self, detail: str = "Anonymous users cannot access this resource"):
        super().__init__(detail=detail)