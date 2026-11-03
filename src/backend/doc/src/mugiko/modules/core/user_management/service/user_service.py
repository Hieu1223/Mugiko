"""User service for user management operations."""
from uuid import UUID
from typing import Optional

from mugiko.modules.core.user_management.persistent.repository import UserRepository
from mugiko.modules.core.user_management.persistent.models import Role
from mugiko.modules.core.user_management.service.dtos import UserProfileResponse, UpdateProfileRequest, AdminUserListResponse, AdminUserDetailResponse, UpdateRoleRequest
from mugiko.common.persistent.session import get_session


class UserService:
    """User service."""
    
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    async def get_my_profile(self, user_id: UUID) -> Optional[UserProfileResponse]:
        """Get current user's profile."""
        user_auth = await self.repository.get_user_auth_by_id(user_id)
        if not user_auth or not user_auth.is_active:
            return None
        
        profile = await self.repository.get_user_profile_by_id(user_id)
        if not profile:
            return None
        
        return UserProfileResponse(
            user_id=user_auth.user_id,
            name=profile.name,
            bio=profile.bio,
            email=profile.email,
            role=user_auth.role,
            joined_at=user_auth.joined_at,
        )
    
    async def update_my_profile(self, user_id: UUID, request: UpdateProfileRequest) -> Optional[UserProfileResponse]:
        """Update current user's profile."""
        user_auth = await self.repository.get_user_auth_by_id(user_id)
        if not user_auth or not user_auth.is_active:
            return None
        
        profile = await self.repository.get_user_profile_by_id(user_id)
        if not profile:
            return None
        
        if request.name is not None:
            profile.name = request.name
        if request.bio is not None:
            profile.bio = request.bio
        if request.email is not None:
            profile.email = request.email
        
        await self.repository.session.flush()
        
        return UserProfileResponse(
            user_id=user_auth.user_id,
            name=profile.name,
            bio=profile.bio,
            email=profile.email,
            role=user_auth.role,
            joined_at=user_auth.joined_at,
        )
    
    async def list_users(self, limit: int = 100, offset: int = 0) -> list[AdminUserListResponse]:
        """List all users for admin."""
        users = await self.repository.list_users(limit, offset)
        result = []
        for user_auth in users:
            profile = await self.repository.get_user_profile_by_id(user_auth.user_id)
            result.append(AdminUserListResponse(
                user_id=user_auth.user_id,
                role=user_auth.role,
                auth_type=user_auth.auth_type,
                auth_id=user_auth.auth_id,
                is_active=user_auth.is_active,
                joined_at=user_auth.joined_at,
                name=profile.name if profile else None,
                email=profile.email if profile else None,
            ))
        return result
    
    async def get_user_detail(self, user_id: UUID) -> Optional[AdminUserDetailResponse]:
        """Get user detail for admin."""
        user_auth = await self.repository.get_user_auth_by_id(user_id)
        if not user_auth:
            return None
        
        profile = await self.repository.get_user_profile_by_id(user_id)
        
        return AdminUserDetailResponse(
            user_id=user_auth.user_id,
            role=user_auth.role,
            auth_type=user_auth.auth_type,
            auth_id=user_auth.auth_id,
            is_active=user_auth.is_active,
            joined_at=user_auth.joined_at,
            name=profile.name if profile else None,
            bio=profile.bio if profile else None,
            email=profile.email if profile else None,
        )
    
    async def update_user_role(self, user_id: UUID, role: Role) -> bool:
        """Update user role."""
        return await self.repository.update_user_role(user_id, role)
    
    async def deactivate_user(self, user_id: UUID) -> bool:
        """Deactivate a user."""
        return await self.repository.deactivate_user(user_id)