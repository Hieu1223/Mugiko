"""Custom exceptions for user_management module."""
from .base import UserManagementException
from .auth import (
    AuthenticationError,
    InvalidTokenError,
    FirebaseTokenError,
    AdminTokenError,
)
from .authorization import AuthorizationError, AnonymousUserError
from .not_found import UserNotFoundError, ProfileNotFoundError
from .conflict import UserAlreadyExistsError
from .validation import InvalidRoleError, ValidationError

__all__ = [
    "UserManagementException",
    "AuthenticationError",
    "InvalidTokenError",
    "FirebaseTokenError",
    "AdminTokenError",
    "AuthorizationError",
    "AnonymousUserError",
    "UserNotFoundError",
    "ProfileNotFoundError",
    "UserAlreadyExistsError",
    "InvalidRoleError",
    "ValidationError",
]