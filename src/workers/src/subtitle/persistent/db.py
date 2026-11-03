"""PostgreSQL plumbing for the subtitle module.

The generic connection helper lives in :mod:`src.common.db`; it is re-exported
here so existing subtitle imports keep working.
"""

from src.common.db import Database

__all__ = ["Database"]
