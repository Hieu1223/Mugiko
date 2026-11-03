"""Subtitle module exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException
from .provider import ProviderNotFoundError, ProviderSyncError, InvalidProviderConfigError
from .subtitle import SubtitleNotFoundError, SubtitleGenerationError, ServiceNotFoundError
from .validation import InvalidVideoURLError, ValidationError
from mugiko.modules.core.job.exceptions import JobNotFoundError

__all__ = [
    "ProviderNotFoundError",
    "ProviderSyncError",
    "InvalidProviderConfigError",
    "SubtitleNotFoundError",
    "SubtitleGenerationError",
    "JobNotFoundError",
    "ServiceNotFoundError",
    "InvalidVideoURLError",
    "ValidationError",
]