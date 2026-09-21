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
from app.schemas.car_image import (
    CarImageCreateRequest,
    CarImageResponse,
)
from app.schemas.car_document import (
    CarDocumentCreateRequest,
    CarDocumentResponse,
    DocumentVerificationRequest,
)
from app.schemas.blackout_period import (
    BlackoutPeriodCreateRequest,
    BlackoutPeriodResponse,
)
from app.schemas.car import (
    CarCreateRequest,
    CarUpdateRequest,
    CarApprovalRequest,
    CarStatusUpdateRequest,
    CarDetailResponse,
    CarPublicResponse,
    PaginatedCarPublicResponse,
    PaginatedCarDetailResponse,
)

from app.schemas.booking import (
    BookingCreateRequest,
    BookingPricingEstimateRequest,
    BookingPricingEstimateResponse,
    BookingPaymentConfirmRequest,
    BookingDecisionRequest,
    BookingDriverAssignRequest,
    BookingCancelRequest,
    BookingStartTripRequest,
    BookingEndTripRequest,
    BookingCarSummary,
    BookingResponse,
    PaginatedBookingResponse,
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
    "CarImageCreateRequest",
    "CarImageResponse",
    "CarDocumentCreateRequest",
    "CarDocumentResponse",
    "DocumentVerificationRequest",
    "BlackoutPeriodCreateRequest",
    "BlackoutPeriodResponse",
    "CarCreateRequest",
    "CarUpdateRequest",
    "CarApprovalRequest",
    "CarStatusUpdateRequest",
    "CarDetailResponse",
    "CarPublicResponse",
    "PaginatedCarPublicResponse",
    "PaginatedCarDetailResponse",
    "BookingCreateRequest",
    "BookingPricingEstimateRequest",
    "BookingPricingEstimateResponse",
    "BookingPaymentConfirmRequest",
    "BookingDecisionRequest",
    "BookingDriverAssignRequest",
    "BookingCancelRequest",
    "BookingStartTripRequest",
    "BookingEndTripRequest",
    "BookingCarSummary",
    "BookingResponse",
    "PaginatedBookingResponse",
]
