"""Base exception for user_management module."""
from typing import Optional
from fastapi import HTTPException, status


class UserManagementException(HTTPException):
    """Base exception for user management module."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: Optional[dict] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or self.__class__.__name__