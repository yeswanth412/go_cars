"""Authentication and User Lifecycle Service.

Orchestrates business logic for:
- User registration with duplicate detection & Argon2 hashing
- Credential validation and JWT access token issuance
- User profile extraction
"""

from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)


class AuthService:
    """Service implementing authentication rules and user flows."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def _build_user_response(self, user: User) -> UserResponse:
        """Helper to construct safe UserResponse from User model."""
        roles: List[str] = [role.name for role in user.roles] if user.roles else []
        return UserResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=roles,
            created_at=user.created_at,
        )

    def register_user(self, request: RegisterRequest) -> UserResponse:
        """Register a new customer account.

        Validates uniqueness of email and phone number, hashes the password
        using Argon2, assigns the default CUSTOMER role, and initializes
        the customer profile in a single atomic transaction.

        Raises:
            HTTPException: 409 Conflict if email or phone is already registered.
        """
        # 1. Check for duplicate email
        normalized_email = request.email.strip().lower()
        if self.user_repo.get_by_email(normalized_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        # 2. Check for duplicate phone number
        cleaned_phone = request.phone_number.strip()
        if self.user_repo.get_by_phone(cleaned_phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already registered",
            )

        # 3. Hash password using Argon2
        hashed_pwd = hash_password(request.password)

        # 4. Atomically persist user and assign default CUSTOMER role
        try:
            user = self.user_repo.create_user(
                full_name=request.full_name.strip(),
                email=normalized_email,
                phone_number=cleaned_phone,
                hashed_password=hashed_pwd,
                role_names=[RoleName.CUSTOMER.value],
            )
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise

        return self._build_user_response(user)

    def authenticate_user(self, request: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue a signed JWT access token.

        Uses generic error message for incorrect credentials to protect
        against email enumeration attacks.

        Raises:
            HTTPException: 401 Unauthorized on invalid credentials or inactive account.
        """
        normalized_email = request.email.strip().lower()
        user = self.user_repo.get_by_email(normalized_email)

        # Constant-time comparison or generic failure if user not found
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive. Please contact support.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate JWT access token with user roles claim
        user_roles: List[str] = [r.name for r in user.roles]
        token = create_access_token(
            subject=str(user.id),
            extra_claims={"roles": user_roles, "email": user.email},
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=self._build_user_response(user),
        )
