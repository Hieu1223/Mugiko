"""Auth context middleware."""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mugiko.common.config.config import settings
from mugiko.modules.core.user_management.service.auth_service import AuthService
from mugiko.modules.core.user_management.persistent.repository import UserRepository
from mugiko.modules.core.user_management.persistent.models import Role, AuthType
from mugiko.modules.core.user_management.service.dtos import AuthContext
from mugiko.common.persistent.session import get_session_cm


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set auth context on request state."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Routes that don't require auth (health, docs, etc.)
        self.public_paths = {
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/api/v1/builtin-provider/info",
            "/api/v1/manga/providers/public",
            "/api/v1/users/register",
        }
        # Public path prefixes (for paths with parameters)
        self.public_prefixes = {
            "/api/v1/builtin-provider/",
        }

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in self.public_paths:
            return True
        for prefix in self.public_prefixes:
            if path.startswith(prefix):
                return True
        return False

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        path = request.url.path
        if self._is_public_path(path):
            return await call_next(request)

        # Get authorization header
        auth_header = request.headers.get("Authorization", "")

        # If no auth header, return 401
        if not auth_header.startswith("Bearer "):
            return Response(
                content='{"detail": "Authorization header required"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        try:
            async with get_session_cm() as session:
                repo = UserRepository(session)
                auth_service = AuthService(repo)

                auth_context = None

                # Determine token type by prefix
                if token.startswith("user-"):
                    firebase_token = token[5:]
                    firebase_user = await auth_service.verify_firebase_token(firebase_token)
                    if firebase_user:
                        user_auth = await repo.get_user_auth_by_auth_id(AuthType.FIREBASE, firebase_user.uid)
                        if user_auth and user_auth.is_active:
                            auth_context = AuthContext(user_id=user_auth.user_id, role=user_auth.role)

                elif token.startswith("admin-"):
                    admin_token = token[6:]
                    auth_context = await auth_service.verify_admin_token(admin_token)

                elif token.startswith("anonymous-"):
                    anon_token = token[10:]
                    auth_context = await auth_service.verify_anonymous_token(anon_token)

                if auth_context is None:
                    return Response(
                        content='{"detail": "Invalid or expired token"}',
                        status_code=401,
                        media_type="application/json",
                    )

                if auth_context and not await self._is_user_active(repo, auth_context.user_id):
                    return Response(
                        content='{"detail": "User account is deactivated"}',
                        status_code=403,
                        media_type="application/json",
                    )

                request.state.auth = auth_context
                request.state.auth_token_info = {
                    "role": auth_context.role,
                    "user_id": auth_context.user_id,
                }

                response = await call_next(request)

                if auth_context:
                    if auth_context.role == Role.ADMIN:
                        response.headers["Authorization"] = f"Bearer admin-{settings.admin_token}"
                    elif auth_context.role == Role.USER:
                        response.headers["Authorization"] = "Bearer user-***"
                    elif auth_context.role == Role.ANONYMOUS:
                        response.headers["Authorization"] = "Bearer anonymous-***"
                else:
                    response.headers["Authorization"] = "Bearer ***"

                return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

    async def _is_user_active(self, repo: UserRepository, user_id) -> bool:
        """Check if user is active."""
        user_auth = await repo.get_user_auth_by_id(user_id)
        return user_auth is not None and user_auth.is_active
