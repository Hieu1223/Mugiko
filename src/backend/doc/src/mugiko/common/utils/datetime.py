"""Datetime utilities."""
from datetime import datetime, timezone


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)