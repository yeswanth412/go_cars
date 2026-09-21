"""User Profile Service.

Handles business rules and transactional logic for general user profiles.
"""

from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserProfileResponse, UserProfileUpdateRequest


class UserService:
    """Service managing authenticated user profiles."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def get_profile(self, user: User) -> UserProfileResponse:
        """Return safe user profile schema representation."""
        roles: List[str] = [role.name for role in user.roles] if user.roles else []
        return UserProfileResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=roles,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def update_profile(self, user: User, request: UserProfileUpdateRequest) -> UserProfileResponse:
        """Partially update user full_name and phone_number.

        Validates phone uniqueness against other user accounts.
        Transactions are strictly committed on success and rolled back on failure.

        Raises:
            HTTPException: 409 Conflict if phone number is already registered to another user.
        """
        update_data = request.model_dump(exclude_unset=True)

        if not update_data:
            return self.get_profile(user)

        new_phone = update_data.get("phone_number")
        if new_phone and new_phone != user.phone_number:
            existing_user = self.user_repo.get_by_phone(new_phone)
            if existing_user and existing_user.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number is already registered to another account",
                )

        try:
            updated_user = self.user_repo.update_profile(
                user=user,
                full_name=update_data.get("full_name"),
                phone_number=new_phone,
            )
            self.db.commit()
            self.db.refresh(updated_user)
        except Exception:
            self.db.rollback()
            raise

        return self.get_profile(updated_user)
