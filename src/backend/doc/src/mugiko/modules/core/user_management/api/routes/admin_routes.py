"""Admin routes."""
from fastapi import APIRouter, Depends, Response, status
from uuid import UUID

from mugiko.modules.core.user_management.api.schemas import (
    AdminUserListResponse,
    AdminUserDetailResponse,
    UpdateRoleRequest,
)
from mugiko.modules.core.user_management.api.dependencies import require_admin, get_bearer_token, get_user_service
from mugiko.modules.core.user_management.service.user_service import UserService
from mugiko.modules.core.user_management.service.dtos import AuthContext, Role, UpdateRoleRequest as ServiceUpdateRoleRequest
from mugiko.modules.core.user_management.exceptions import (
    UserNotFoundError,
    InvalidRoleError,
)


router = APIRouter(prefix="/admin/users", tags=[])


@router.get(
    "",
    response_model=list[AdminUserListResponse],
)
async def list_users(
    response: Response,
    limit: int = 100,
    offset: int = 0,
    auth_context: AuthContext = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """List all users (admin only)."""
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    users = await user_service.list_users(limit, offset)
    return [
        AdminUserListResponse(
            user_id=user.user_id,
            role=user.role.value,
            auth_type=user.auth_type.value,
            auth_id=user.auth_id,
            is_active=user.is_active,
            joined_at=user.joined_at,
            name=user.name,
            email=user.email,
        )
        for user in users
    ]


@router.get(
    "/{user_id}",
    response_model=AdminUserDetailResponse,
)
async def get_user_detail(
    user_id: UUID,
    response: Response,
    auth_context: AuthContext = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """Get user detail (admin only)."""
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    user = await user_service.get_user_detail(user_id)
    if not user:
        raise UserNotFoundError()

    return AdminUserDetailResponse(
        user_id=user.user_id,
        role=user.role.value,
        auth_type=user.auth_type.value,
        auth_id=user.auth_id,
        is_active=user.is_active,
        joined_at=user.joined_at,
        name=user.name,
        bio=user.bio,
        email=user.email,
    )


@router.patch(
    "/{user_id}/role",
    response_model=AdminUserDetailResponse,
)
async def update_user_role(
    user_id: UUID,
    request: UpdateRoleRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """Update user role (admin only)."""
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    # Validate role
    try:
        role = Role(request.role)
    except ValueError:
        raise InvalidRoleError()

    success = await user_service.update_user_role(user_id, role)
    if not success:
        raise UserNotFoundError()

    # Return updated user
    user = await user_service.get_user_detail(user_id)
    if not user:
        raise UserNotFoundError()

    return AdminUserDetailResponse(
        user_id=user.user_id,
        role=user.role.value,
        auth_type=user.auth_type.value,
        auth_id=user.auth_id,
        is_active=user.is_active,
        joined_at=user.joined_at,
        name=user.name,
        bio=user.bio,
        email=user.email,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_user(
    user_id: UUID,
    response: Response,
    auth_context: AuthContext = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """Deactivate a user (admin only). Soft delete - sets is_active to false."""
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    success = await user_service.deactivate_user(user_id)
    if not success:
        raise UserNotFoundError()

    return None