"""General User Profile Routes.

Endpoints:
- GET   /users/me: View authenticated user profile and roles
- PATCH /users/me: Partial update authenticated user profile (full_name, phone_number)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserProfileUpdateRequest
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Retrieve the authenticated user's own profile and active roles.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Fetch current user identity and profile attributes."""
    user_service = UserService(db)
    return user_service.get_profile(current_user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Current User Profile",
    description="Update mutable attributes (full_name, phone_number) for the authenticated user.",
)
def update_current_user_profile(
    request: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Partially update current user's profile."""
    user_service = UserService(db)
    return user_service.update_profile(current_user, request)
