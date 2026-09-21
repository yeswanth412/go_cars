"""Car Fleet Management Pydantic Schemas.

Defines request and response schemas for owner car management, public car search,
and administrative verification.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.enums import CarStatus, FuelType, TransmissionType
from app.schemas.car_image import CarImageResponse
from app.schemas.car_document import CarDocumentResponse
from app.schemas.blackout_period import BlackoutPeriodResponse


class CarCreateRequest(BaseModel):
    """Schema for registering a new vehicle by an owner."""

    brand: str = Field(..., min_length=1, max_length=50, description="Car manufacturer (e.g. Toyota)")
    model: str = Field(..., min_length=1, max_length=50, description="Vehicle model (e.g. Camry)")
    year: int = Field(..., ge=1990, le=datetime.now().year + 1, description="Manufacturing year")
    registration_number: str = Field(..., min_length=4, max_length=30, description="Unique vehicle license plate number")
    fuel_type: FuelType = Field(FuelType.PETROL, description="Vehicle fuel type")
    transmission: TransmissionType = Field(TransmissionType.MANUAL, description="Transmission type")
    seating_capacity: int = Field(..., gt=0, le=50, description="Seating capacity (>0)")
    odometer_km: int = Field(0, ge=0, description="Current odometer reading in kilometers (>=0)")

    # Compliance & Registration
    rc_number: str = Field(..., min_length=3, max_length=50, description="Registration Certificate number")
    insurance_policy_number: str = Field(..., min_length=3, max_length=50, description="Insurance policy identifier")
    insurance_expiry_date: date = Field(..., description="Insurance policy expiration date")

    # Location
    city: str = Field(..., min_length=2, max_length=100, description="Vehicle primary operating city")
    address: str = Field(..., min_length=5, description="Full vehicle station or garage pickup address")

    # Platform-Controlled Initial Pricing (Validated non-negative)
    hourly_rate: Decimal = Field(..., ge=0, description="Hourly rental rate in INR")
    daily_rate: Decimal = Field(..., ge=0, description="Daily rental rate in INR")
    weekly_rate: Decimal = Field(..., ge=0, description="Weekly rental rate in INR")

    # Booking Modes
    is_self_drive_allowed: bool = Field(True, description="Whether car can be rented for self-drive")
    is_driver_allowed: bool = Field(True, description="Whether car can be rented with a driver")

    model_config = ConfigDict(extra="forbid")

    @field_validator("brand", "model", "registration_number", "rc_number", "insurance_policy_number", "city", "address")
    @classmethod
    def clean_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned

    @field_validator("registration_number")
    @classmethod
    def clean_reg_no(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")

    @model_validator(mode="after")
    def validate_booking_modes(self) -> "CarCreateRequest":
        if not self.is_self_drive_allowed and not self.is_driver_allowed:
            raise ValueError("At least one booking mode (self-drive or with-driver) must be enabled")
        return self


class CarUpdateRequest(BaseModel):
    """Schema for updating vehicle operational attributes by the owner.

    Pricing, ownership, status, registration number, and RC number cannot be modified by owners.
    """

    odometer_km: Optional[int] = Field(None, ge=0, description="Updated odometer reading in km")
    insurance_expiry_date: Optional[date] = Field(None, description="Updated insurance expiry date")
    insurance_policy_number: Optional[str] = Field(None, max_length=50, description="Updated insurance policy number")
    city: Optional[str] = Field(None, max_length=100, description="Updated operating city")
    address: Optional[str] = Field(None, description="Updated station address")
    is_self_drive_allowed: Optional[bool] = Field(None, description="Toggle self-drive availability")
    is_driver_allowed: Optional[bool] = Field(None, description="Toggle driver availability")

    model_config = ConfigDict(extra="forbid")

    @field_validator("city", "address", "insurance_policy_number")
    @classmethod
    def clean_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None


class CarApprovalRequest(BaseModel):
    """Administrative vehicle onboarding decision schema."""

    status: CarStatus = Field(..., description="Decision status: must be AVAILABLE or REJECTED")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection (mandatory if REJECTED)")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_approval_status(self) -> "CarApprovalRequest":
        if self.status not in (CarStatus.AVAILABLE, CarStatus.REJECTED):
            raise ValueError("Approval status must be either AVAILABLE or REJECTED")
        if self.status == CarStatus.REJECTED and not self.rejection_reason:
            raise ValueError("rejection_reason is required when rejecting a vehicle")
        return self


class CarStatusUpdateRequest(BaseModel):
    """Administrative operational status update schema."""

    status: CarStatus = Field(
        ...,
        description="Target operational status (AVAILABLE, MAINTENANCE, SUSPENDED, INACTIVE)",
    )

    model_config = ConfigDict(extra="forbid")


class CarDetailResponse(BaseModel):
    """Comprehensive vehicle response schema for owners and administrators."""

    id: UUID
    owner_id: UUID
    brand: str
    model: str
    year: int
    registration_number: str
    fuel_type: FuelType
    transmission: TransmissionType
    seating_capacity: int
    odometer_km: int
    rc_number: str
    insurance_policy_number: str
    insurance_expiry_date: date
    status: CarStatus
    city: str
    address: str
    hourly_rate: Decimal
    daily_rate: Decimal
    weekly_rate: Decimal
    is_self_drive_allowed: bool
    is_driver_allowed: bool
    created_at: datetime
    updated_at: datetime

    images: List[CarImageResponse] = []
    documents: List[CarDocumentResponse] = []
    blackout_periods: List[BlackoutPeriodResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CarPublicResponse(BaseModel):
    """Sanitized public vehicle response schema.

    Strictly excludes sensitive owner identity, exact address, RC number,
    insurance policy details, and compliance documents.
    """

    id: UUID
    brand: str
    model: str
    year: int
    fuel_type: FuelType
    transmission: TransmissionType
    seating_capacity: int
    city: str
    status: CarStatus
    hourly_rate: Decimal
    daily_rate: Decimal
    weekly_rate: Decimal
    is_self_drive_allowed: bool
    is_driver_allowed: bool
    images: List[CarImageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedCarPublicResponse(BaseModel):
    """Paginated response for public car discovery."""

    total: int = Field(..., description="Total count of available matching cars")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    items: List[CarPublicResponse] = Field(..., description="List of publicly available vehicles")


class PaginatedCarDetailResponse(BaseModel):
    """Paginated response for administrative and owner car listings."""

    total: int = Field(..., description="Total count of cars")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    items: List[CarDetailResponse] = Field(..., description="List of vehicle details")
