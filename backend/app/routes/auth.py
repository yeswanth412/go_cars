"""Authentication and User Account Routes.

Endpoints:
- POST /register: Customer self-registration
- POST /login: Issue JWT access token
- GET  /me: View authenticated user profile
- GET  /admin-test: Role verification test endpoint (ADMIN)
- GET  /owner-test: Role verification test endpoint (OWNER)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.services.auth_service import AuthService
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Customer Account",
    description="Create a new customer user with default CUSTOMER role and initialize profile.",
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """Handle new customer registration."""
    auth_service = AuthService(db)
    user_response = auth_service.register_user(request)
    return RegisterResponse(
        message="User registered successfully",
        user=user_response,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate with email and password to receive a signed Bearer JWT token.",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verify credentials and issue JWT access token."""
    auth_service = AuthService(db)
    return auth_service.authenticate_user(request)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current User Profile",
    description="Fetch profile and assigned roles for the currently authenticated user.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user's profile and active roles."""
    roles = [role.name for role in current_user.roles] if current_user.roles else []
    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        roles=roles,
        created_at=current_user.created_at,
    )


# =============================================================================
# Development / Verification Role-Protected Endpoints (Marked for Dev Testing)
# =============================================================================

@router.get(
    "/admin-test",
    status_code=status.HTTP_200_OK,
    summary="[Dev] Admin Role Test Endpoint",
    description="Verification endpoint requiring the ADMIN role.",
)
def admin_role_test(
    current_user: User = Depends(require_roles(RoleName.ADMIN.value)),
):
    """Test endpoint accessible only to administrators."""
    return {
        "message": "Admin authorization verified successfully",
        "email": current_user.email,
        "roles": [r.name for r in current_user.roles],
    }


@router.get(
    "/owner-test",
    status_code=status.HTTP_200_OK,
    summary="[Dev] Owner Role Test Endpoint",
    description="Verification endpoint requiring the OWNER role.",
)
def owner_role_test(
    current_user: User = Depends(require_roles(RoleName.OWNER.value)),
):
    """Test endpoint accessible to car owners and multi-role owner accounts."""
    return {
        "message": "Owner authorization verified successfully",
        "email": current_user.email,
        "roles": [r.name for r in current_user.roles],
    }
