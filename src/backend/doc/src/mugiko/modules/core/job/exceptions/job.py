"""Job exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException


class JobNotFoundError(UserManagementException):
    def __init__(self, detail: str = "Job not found"):
        super().__init__(detail=detail, status_code=404)