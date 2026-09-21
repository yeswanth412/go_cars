"""Pydantic data schemas for request validation and response serialization."""

from app.schemas.health import HealthCheckResponse
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.user import (
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.schemas.customer import (
    CustomerProfileResponse,
    CustomerProfileUpdateRequest,
)
from app.schemas.owner import (
    OwnerProfileResponse,
    OwnerProfileUpdateRequest,
)
from app.schemas.driver import (
    DriverProfileResponse,
    DriverProfileUpdateRequest,
)
from app.schemas.admin import (
    RoleAssignRequest,
    UserStatusUpdateRequest,
    UserDetailResponse,
    PaginatedUserResponse,
)

__all__ = [
    "HealthCheckResponse",
    "RegisterRequest",
    "RegisterResponse",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "UserProfileResponse",
    "UserProfileUpdateRequest",
    "CustomerProfileResponse",
    "CustomerProfileUpdateRequest",
    "OwnerProfileResponse",
    "OwnerProfileUpdateRequest",
    "DriverProfileResponse",
    "DriverProfileUpdateRequest",
    "RoleAssignRequest",
    "UserStatusUpdateRequest",
    "UserDetailResponse",
    "PaginatedUserResponse",
]
