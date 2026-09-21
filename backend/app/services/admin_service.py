"""Admin User and Role Management Service.

Encapsulates administrative workflows, RBAC role assignments and revocations,
account status updates, and safety checks (e.g. final admin safeguards).
"""

from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository
from app.repositories.owner_repository import OwnerRepository
from app.repositories.user_repository import UserRepository
from app.schemas.customer import CustomerProfileResponse
from app.schemas.driver import DriverProfileResponse
from app.schemas.owner import OwnerProfileResponse
from app.schemas.admin import UserDetailResponse, PaginatedUserResponse


class AdminService:
    """Service implementing administrative user and role management operations."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.owner_repo = OwnerRepository(db)

    def _build_user_detail(self, user: User) -> UserDetailResponse:
        """Construct UserDetailResponse model instance safely."""
        roles: List[str] = [role.name for role in user.roles] if user.roles else []

        cust_profile = None
        if user.customer_profile:
            cust_profile = CustomerProfileResponse.model_validate(user.customer_profile)

        own_profile = None
        if user.owner_profile:
            own_profile = OwnerProfileResponse.model_validate(user.owner_profile)

        drv_profile = None
        if user.driver_profile:
            drv_profile = DriverProfileResponse.model_validate(user.driver_profile)

        return UserDetailResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=roles,
            customer_profile=cust_profile,
            owner_profile=own_profile,
            driver_profile=drv_profile,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        role: Optional[str] = None,
    ) -> PaginatedUserResponse:
        """Query users with pagination and filtering."""
        users, total = self.user_repo.list_users(
            page=page,
            page_size=page_size,
            search=search,
            is_active=is_active,
            role_name=role,
        )
        items = [self._build_user_detail(u) for u in users]
        return PaginatedUserResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    def get_user_details(self, user_id: UUID) -> UserDetailResponse:
        """Retrieve full user details by user ID."""
        user = self.user_repo.get_user_with_profiles(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return self._build_user_detail(user)

    def assign_role(self, user_id: UUID, role_name: RoleName) -> UserDetailResponse:
        """Assign an additional role to a user.

        Raises:
            HTTPException: 404 if user not found.
            HTTPException: 409 if role is already assigned.
        """
        user = self.user_repo.get_user_with_profiles(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        existing_role_names = [r.name for r in user.roles]
        if role_name.value in existing_role_names:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{role_name.value}' is already assigned to this user",
            )

        try:
            self.user_repo.add_role_to_user(user_id, role_name.value)

            # Initialize corresponding profile if needed
            if role_name == RoleName.OWNER and not user.owner_profile:
                self.owner_repo.create_or_get(user_id)
            elif role_name == RoleName.CUSTOMER and not user.customer_profile:
                self.customer_repo.create_or_get(user_id)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.user_repo.get_user_with_profiles(user_id)
        return self._build_user_detail(refreshed or user)

    def revoke_role(
        self,
        user_id: UUID,
        role_name: str,
        current_admin_id: UUID,
    ) -> UserDetailResponse:
        """Revoke a role from a user.

        Enforces safeguards:
        - Rejects revoking ADMIN role if the target is the last active administrator.

        Raises:
            HTTPException: 404 if user not found or role not found on user.
            HTTPException: 400 if attempting to remove the final administrator.
        """
        user = self.user_repo.get_user_with_profiles(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        existing_role_names = [r.name for r in user.roles]
        if role_name not in existing_role_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User does not possess role '{role_name}'",
            )

        # Safeguard: Prevent removing final active administrator
        if role_name == RoleName.ADMIN.value:
            active_admin_count = self.user_repo.count_active_admins()
            if user.is_active and active_admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot revoke the ADMIN role from the final active administrator",
                )

        try:
            self.user_repo.remove_role_from_user(user_id, role_name)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.user_repo.get_user_with_profiles(user_id)
        return self._build_user_detail(refreshed or user)

    def update_user_status(
        self,
        user_id: UUID,
        is_active: bool,
        current_admin_id: UUID,
    ) -> UserDetailResponse:
        """Activate or deactivate a user account.

        Enforces safeguards:
        - Administrators cannot deactivate their own account.
        - Cannot deactivate the final active administrator.

        Raises:
            HTTPException: 404 if user not found.
            HTTPException: 400 if deactivation violates administrative safeguards.
        """
        user = self.user_repo.get_user_with_profiles(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if not is_active:
            if user.id == current_admin_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Administrators cannot deactivate their own account",
                )

            # Check if this user is the final active admin
            user_roles = [r.name for r in user.roles]
            if RoleName.ADMIN.value in user_roles and user.is_active:
                active_admin_count = self.user_repo.count_active_admins()
                if active_admin_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot deactivate the final active administrator",
                    )

        try:
            self.user_repo.update_status(user, is_active)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.user_repo.get_user_with_profiles(user_id)
        return self._build_user_detail(refreshed or user)
