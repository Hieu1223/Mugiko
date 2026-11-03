"""Role-based access control dependencies."""
from fastapi import Depends, HTTPException, Request, status, Header
from typing import Optional, AsyncGenerator

from mugiko.modules.core.user_management.service.dtos import AuthContext, Role
from mugiko.modules.core.user_management.service.auth_service import AuthService
from mugiko.modules.core.user_management.service.user_service import UserService
from mugiko.modules.core.user_management.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AnonymousUserError,
)
from mugiko.common.persistent.session import get_session_cm


def get_auth_context(request: Request) -> AuthContext:
    """Get auth context from request state."""
    if not hasattr(request.state, 'auth') or request.state.auth is None:
        raise AuthenticationError()
    return request.state.auth


def require_roles(*allowed_roles: Role):
    """Dependency to require specific roles."""
    def role_checker(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth_context.role not in allowed_roles:
            raise AuthorizationError(
                detail=f"Role {auth_context.role.value} not allowed. Required: {[r.value for r in allowed_roles]}"
            )
        return auth_context
    return role_checker


# Common role dependencies
require_user = require_roles(Role.USER, Role.ADMIN)
require_admin = require_roles(Role.ADMIN)


async def get_bearer_token(authorization: str = Header(None)) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise AuthenticationError(detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise AuthenticationError(detail="Invalid authorization header format. Expected 'Bearer <token>'")
    return authorization[7:]  # Remove 'Bearer ' prefix


async def get_auth_service() -> AsyncGenerator[AuthService, None]:
    """Get auth service dependency."""
    async with get_session_cm() as session:
        from mugiko.modules.core.user_management.persistent.repository import UserRepository
        repo = UserRepository(session)
        yield AuthService(repo)


async def get_user_service() -> AsyncGenerator[UserService, None]:
    """Get user service dependency."""
    async with get_session_cm() as session:
        from mugiko.modules.core.user_management.persistent.repository import UserRepository
        repo = UserRepository(session)
        yield UserService(repo)