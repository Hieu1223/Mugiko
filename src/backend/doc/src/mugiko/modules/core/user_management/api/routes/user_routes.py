"""User routes."""
from fastapi import APIRouter, Depends, Header, Response, status, Security
from uuid import UUID

from mugiko.modules.core.user_management.api.schemas import (
    RegisterRequest,
    RegisterResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from mugiko.modules.core.user_management.api.dependencies import require_user, get_bearer_token, get_auth_service, get_user_service
from mugiko.modules.core.user_management.service.auth_service import AuthService
from mugiko.modules.core.user_management.service.user_service import UserService
from mugiko.modules.core.user_management.service.dtos import AuthContext, RegisterRequest as ServiceRegisterRequest, UpdateProfileRequest
from mugiko.modules.core.user_management.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    FirebaseTokenError,
    UserAlreadyExistsError,
    ProfileNotFoundError,
    AuthorizationError,
    AnonymousUserError,
)


router = APIRouter(prefix="/users", tags=[])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    request: RegisterRequest,
    response: Response,
    bearer_token: str = Depends(get_bearer_token),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user with Firebase authentication.

    Requires a valid `user-<firebase_id_token>` bearer token.
    """
    if not bearer_token.startswith("user-"):
        raise InvalidTokenError(detail="Invalid token format. Expected 'user-<firebase_id_token>'")

    firebase_token = bearer_token[5:]  # Remove 'user-' prefix
    firebase_user = await auth_service.verify_firebase_token(firebase_token)

    if not firebase_user:
        raise FirebaseTokenError()

    service_request = ServiceRegisterRequest(
        firebase_uid=firebase_user.uid,
        name=request.name,
        bio=request.bio,
        email=request.email,
    )
    result = await auth_service.register_user(service_request, firebase_user)

    # Echo the bearer token in response header
    response.headers["Authorization"] = f"Bearer {result.token}"

    return RegisterResponse(
        user_id=result.user_id,
        role=result.role.value,
        token=result.token,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
)
async def get_my_profile(
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get current user's profile."""
    # Add Authorization header to response
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    profile = await user_service.get_my_profile(auth_context.user_id)
    if not profile:
        raise ProfileNotFoundError()

    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        bio=profile.bio,
        email=profile.email,
        role=profile.role.value,
        joined_at=profile.joined_at,
    )


@router.patch(
    "/me/profile",
    response_model=UserProfileResponse,
)
async def update_my_profile(
    request: UserProfileUpdate,
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update current user's profile."""
    # Add Authorization header to response
    response.headers["Authorization"] = response.headers.get("Authorization", "Bearer ***")

    update_request = UpdateProfileRequest(
        name=request.name,
        bio=request.bio,
        email=request.email,
    )
    profile = await user_service.update_my_profile(auth_context.user_id, update_request)
    if not profile:
        raise ProfileNotFoundError()

    return UserProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        bio=profile.bio,
        email=profile.email,
        role=profile.role.value,
        joined_at=profile.joined_at,
    )