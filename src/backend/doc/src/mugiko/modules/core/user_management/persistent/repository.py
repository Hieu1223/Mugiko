"""Repository for user management database operations."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mugiko.modules.core.user_management.persistent.models import UserAuth, UserProfile, Role, AuthType
from mugiko.modules.core.user_management.persistent.dtos import UserAuthDTO, UserProfileDTO, CreateUserAuthDTO, CreateUserProfileDTO


class UserRepository:
    """Repository for user management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_user_auth(self, dto: CreateUserAuthDTO) -> UserAuth:
        """Create a new user auth record."""
        user_auth = UserAuth(
            role=dto.role,
            auth_type=dto.auth_type,
            auth_id=dto.auth_id,
            is_active=dto.is_active,
        )
        self.session.add(user_auth)
        await self.session.flush()
        return user_auth
    
    async def create_user_profile(self, dto: CreateUserProfileDTO) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(
            user_id=dto.user_id,
            name=dto.name,
            bio=dto.bio,
            email=dto.email,
        )
        self.session.add(profile)
        await self.session.flush()
        return profile
    
    async def get_user_auth_by_auth_id(self, auth_type: AuthType, auth_id: str) -> Optional[UserAuth]:
        """Get user auth by auth_type and auth_id."""
        stmt = select(UserAuth).where(
            UserAuth.auth_type == auth_type,
            UserAuth.auth_id == auth_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_auth_by_id(self, user_id: UUID) -> Optional[UserAuth]:
        """Get user auth by user_id."""
        stmt = select(UserAuth).where(UserAuth.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_profile_by_id(self, user_id: UUID) -> Optional[UserProfile]:
        """Get user profile by user_id."""
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_with_profile(self, user_id: UUID) -> Optional[tuple[UserAuth, Optional[UserProfile]]]:
        """Get user auth with profile."""
        stmt = select(UserAuth).where(UserAuth.user_id == user_id)
        result = await self.session.execute(stmt)
        user_auth = result.scalar_one_or_none()
        if not user_auth:
            return None
        profile = await self.get_user_profile_by_id(user_id)
        return (user_auth, profile)
    
    async def list_users(self, limit: int = 100, offset: int = 0) -> List[UserAuth]:
        """List users with pagination."""
        stmt = select(UserAuth).order_by(UserAuth.joined_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_user_role(self, user_id: UUID, role: Role) -> bool:
        """Update user role."""
        stmt = update(UserAuth).where(UserAuth.user_id == user_id).values(role=role)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def deactivate_user(self, user_id: UUID) -> bool:
        """Deactivate a user (soft delete)."""
        stmt = update(UserAuth).where(UserAuth.user_id == user_id).values(is_active=False)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def count_users(self) -> int:
        """Count total users."""
        from sqlalchemy import func
        stmt = select(func.count(UserAuth.user_id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def admin_exists(self) -> bool:
        """Check if any admin user exists."""
        stmt = select(UserAuth).where(UserAuth.role == Role.ADMIN).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None