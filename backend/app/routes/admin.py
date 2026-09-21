"""Administrative User and Role Management Routes.

Endpoints:
- GET    /admin/users: Paginated list of users with search and filter support
- GET    /admin/users/{user_id}: Detailed user inspection with roles and profiles
- POST   /admin/users/{user_id}/roles: Assign role to user
- DELETE /admin/users/{user_id}/roles/{role_name}: Revoke role from user
- PATCH  /admin/users/{user_id}/status: Activate / deactivate user account
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.admin import (
    RoleAssignRequest,
    UserStatusUpdateRequest,
    UserDetailResponse,
    PaginatedUserResponse,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin Management"])


@router.get(
    "/users",
    response_model=PaginatedUserResponse,
    status_code=status.HTTP_200_OK,
    summary="List Users (Admin)",
    description="Retrieve paginated list of users with optional filtering and search. Requires ADMIN role.",
)
def list_users(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of users per page (max 100)"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role name (ADMIN, CUSTOMER, OWNER, DRIVER)"),
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> PaginatedUserResponse:
    """List users with pagination and search criteria."""
    admin_service = AdminService(db)
    return admin_service.list_users(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        role=role,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Details (Admin)",
    description="Retrieve comprehensive details for a specific user. Requires ADMIN role.",
)
def get_user_details(
    user_id: UUID,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Inspect full user record including roles and linked profiles."""
    admin_service = AdminService(db)
    return admin_service.get_user_details(user_id)


@router.post(
    "/users/{user_id}/roles",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Role to User (Admin)",
    description="Assign an additional system role to a user. Requires ADMIN role.",
)
def assign_role(
    user_id: UUID,
    request: RoleAssignRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Assign system role to target user."""
    admin_service = AdminService(db)
    return admin_service.assign_role(user_id, request.role)


@router.delete(
    "/users/{user_id}/roles/{role_name}",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Role from User (Admin)",
    description="Revoke a system role from a user. Safeguards prevent removing the final active administrator. Requires ADMIN role.",
)
def revoke_role(
    user_id: UUID,
    role_name: str,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Revoke system role from target user."""
    admin_service = AdminService(db)
    return admin_service.revoke_role(user_id, role_name.upper(), current_admin.id)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Account Status (Admin)",
    description="Activate or deactivate a user account. Deactivated users cannot authenticate. Prevents self-deactivation. Requires ADMIN role.",
)
def update_user_status(
    user_id: UUID,
    request: UserStatusUpdateRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Activate or deactivate user account."""
    admin_service = AdminService(db)
    return admin_service.update_user_status(user_id, request.is_active, current_admin.id)


from pydantic import BaseModel, ConfigDict
from app.models.enums import DriverVerificationStatus
from app.schemas.driver import DriverProfileResponse


class DriverVerificationUpdateRequest(BaseModel):
    verification_status: DriverVerificationStatus
    model_config = ConfigDict(extra="forbid")


@router.patch(
    "/drivers/{user_id}/verification",
    response_model=DriverProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Driver (Admin)",
    description="Approve or reject a commercial driver profile. Requires ADMIN role.",
)
def update_driver_verification(
    user_id: UUID,
    request: DriverVerificationUpdateRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> DriverProfileResponse:
    """Admin approves or rejects a driver's verification status."""
    from sqlalchemy import select
    from app.models.user import User as UserModel
    driver_user = db.scalars(select(UserModel).where(UserModel.id == user_id)).first()
    if not driver_user or not driver_user.driver_profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    driver_user.driver_profile.verification_status = request.verification_status.value
    db.commit()
    db.refresh(driver_user.driver_profile)
    return DriverProfileResponse.model_validate(driver_user.driver_profile)
