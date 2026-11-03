"""Authentication service."""
import secrets
from uuid import UUID

from mugiko.modules.core.user_management.provider.firebase_provider import FirebaseProvider
from mugiko.modules.core.user_management.persistent.repository import UserRepository
from mugiko.modules.core.user_management.persistent.models import Role, AuthType
from mugiko.modules.core.user_management.persistent.dtos import CreateUserAuthDTO, CreateUserProfileDTO
from mugiko.modules.core.user_management.service.dtos import AuthContext, RegisterRequest, RegisterResponse
from mugiko.modules.core.user_management.provider.dtos import FirebaseUserInfo
from mugiko.modules.core.user_management.exceptions import UserAlreadyExistsError
from mugiko.common.persistent.session import get_session_cm


class AuthService:
    """Authentication service."""
    
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    async def verify_firebase_token(self, id_token: str) -> FirebaseUserInfo | None:
        """Verify Firebase ID token."""
        return FirebaseProvider.verify_id_token(id_token)
    
    async def verify_admin_token(self, token: str) -> AuthContext | None:
        """Verify admin token."""
        user_auth = await self.repository.get_user_auth_by_auth_id(AuthType.ADMIN, token)
        if not user_auth or not user_auth.is_active or user_auth.role != Role.ADMIN:
            return None
        return AuthContext(user_id=user_auth.user_id, role=user_auth.role)
    
    async def verify_anonymous_token(self, token: str) -> AuthContext | None:
        """Verify anonymous token."""
        user_auth = await self.repository.get_user_auth_by_auth_id(AuthType.ANONYMOUS, token)
        if not user_auth or not user_auth.is_active:
            return None
        return AuthContext(user_id=user_auth.user_id, role=user_auth.role)
    
    async def create_anonymous_user(self) -> tuple[AuthContext, str]:
        """Create an anonymous user and return auth context and token."""
        token = secrets.token_urlsafe(32)
        async with get_session_cm() as session:
            repo = UserRepository(session)
            user_auth = await repo.create_user_auth(CreateUserAuthDTO(
                role=Role.ANONYMOUS,
                auth_type=AuthType.ANONYMOUS,
                auth_id=token,
                is_active=True,
            ))
            return AuthContext(user_id=user_auth.user_id, role=user_auth.role), f"anonymous-{token}"
    
    async def register_user(self, request: RegisterRequest, firebase_user: FirebaseUserInfo) -> RegisterResponse:
        """Register a new user from Firebase."""
        # Check if Firebase UID already exists
        async with get_session_cm() as session:
            repo = UserRepository(session)
            existing = await repo.get_user_auth_by_auth_id(AuthType.FIREBASE, firebase_user.uid)
            if existing:
                raise UserAlreadyExistsError()
            
            # Create user_auth and profile in one transaction
            user_auth = await repo.create_user_auth(CreateUserAuthDTO(
                role=Role.USER,
                auth_type=AuthType.FIREBASE,
                auth_id=firebase_user.uid,
                is_active=True,
            ))
            
            await repo.create_user_profile(CreateUserProfileDTO(
                user_id=user_auth.user_id,
                name=request.name,
                bio=request.bio,
                email=request.email or firebase_user.email,
            ))
            
            token = f"user-{firebase_user.uid}"
            return RegisterResponse(
                user_id=user_auth.user_id,
                role=user_auth.role,
                token=token,
            )
    
    async def get_user_auth(self, user_id: UUID) -> AuthContext | None:
        """Get auth context for user."""
        user_auth = await self.repository.get_user_auth_by_id(user_id)
        if not user_auth or not user_auth.is_active:
            return None
        return AuthContext(user_id=user_auth.user_id, role=user_auth.role)
