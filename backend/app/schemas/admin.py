"""Admin User and Role Management Schemas.

Defines schemas for administrative queries, user inspection, role assignments,
and account lifecycle management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import RoleName
from app.schemas.customer import CustomerProfileResponse
from app.schemas.owner import OwnerProfileResponse
from app.schemas.driver import DriverProfileResponse


class RoleAssignRequest(BaseModel):
    """Request payload to assign a system role to a user."""

    role: RoleName = Field(..., description="Role to assign (ADMIN, CUSTOMER, OWNER, DRIVER)")

    model_config = ConfigDict(extra="forbid")


class UserStatusUpdateRequest(BaseModel):
    """Request payload to activate or deactivate a user account."""

    is_active: bool = Field(..., description="Account active status flag (True = active, False = deactivated)")

    model_config = ConfigDict(extra="forbid")


class UserDetailResponse(BaseModel):
    """Detailed user inspection schema for administrators.

    Includes user account identity, roles, and linked domain profiles.
    Never exposes password hashes or security credentials.
    """

    id: UUID
    full_name: str
    email: str
    phone_number: str
    is_active: bool
    is_verified: bool
    roles: List[str]
    customer_profile: Optional[CustomerProfileResponse] = None
    owner_profile: Optional[OwnerProfileResponse] = None
    driver_profile: Optional[DriverProfileResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUserResponse(BaseModel):
    """Paginated user listing response."""

    total: int = Field(..., description="Total count of matching users")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of records per page")
    items: List[UserDetailResponse] = Field(..., description="List of user details for the current page")
