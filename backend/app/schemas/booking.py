"""Booking Transaction Pydantic Schemas.

Defines schemas for:
- Customer booking creation and pricing previews
- Mock payment confirmations
- Owner decisions (accept/reject)
- Driver assignments
- Trip lifecycle operations (start trip, complete trip with odometer readings)
- Cancellations and refunds
- Serialized responses and pagination
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.enums import BookingType, RentalType, BookingStatus


class BookingCreateRequest(BaseModel):
    """Schema for a customer requesting a vehicle rental."""

    car_id: UUID = Field(..., description="Unique ID of vehicle to rent")
    booking_type: BookingType = Field(BookingType.SELF_DRIVE, description="SELF_DRIVE or WITH_DRIVER")
    rental_type: RentalType = Field(RentalType.DAILY, description="HOURLY, DAILY, or WEEKLY")
    start_time: datetime = Field(..., description="Reservation start timestamp in UTC (must be in future)")
    end_time: datetime = Field(..., description="Reservation end timestamp in UTC (must be after start_time)")
    pickup_location: str = Field(..., min_length=3, description="Station or street pickup address")
    dropoff_location: str = Field(..., min_length=3, description="Station or street return address")

    model_config = ConfigDict(extra="forbid")

    @field_validator("pickup_location", "dropoff_location")
    @classmethod
    def clean_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Location cannot be empty or whitespace only")
        return cleaned

    @model_validator(mode="after")
    def validate_time_window(self) -> "BookingCreateRequest":
        now = datetime.now(timezone.utc)
        if self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)
        if self.end_time.tzinfo is None:
            self.end_time = self.end_time.replace(tzinfo=timezone.utc)

        if self.start_time <= now:
            raise ValueError("Reservation start_time must be strictly in the future")
        if self.end_time <= self.start_time:
            raise ValueError("Reservation end_time must be strictly after start_time")
        return self


class BookingPricingEstimateRequest(BaseModel):
    """Request payload to preview rental price breakdown before booking."""

    car_id: UUID
    booking_type: BookingType = BookingType.SELF_DRIVE
    rental_type: RentalType = RentalType.DAILY
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_time_window(self) -> "BookingPricingEstimateRequest":
        if self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)
        if self.end_time.tzinfo is None:
            self.end_time = self.end_time.replace(tzinfo=timezone.utc)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class BookingPricingEstimateResponse(BaseModel):
    """Detailed price calculation breakdown preview."""

    car_id: UUID
    booking_type: BookingType
    rental_type: RentalType
    duration_hours: Decimal
    billable_units: int
    unit_rate: Decimal
    base_amount: Decimal
    driver_charge: Decimal
    platform_fee: Decimal
    tax_amount: Decimal
    security_deposit: Decimal
    total_amount: Decimal
    currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)


class BookingPaymentConfirmRequest(BaseModel):
    """Mock payment execution confirmation payload."""

    payment_method: str = Field("MOCK_UPI", description="Mock payment method (MOCK_UPI, MOCK_CARD, etc.)")
    transaction_reference: Optional[str] = Field(None, description="Optional bank gateway reference string")

    model_config = ConfigDict(extra="forbid")


class BookingDecisionRequest(BaseModel):
    """Owner or administrator acceptance/rejection decision payload."""

    decision: str = Field(..., description="Decision: ACCEPT (to confirm) or REJECT")
    rejection_reason: Optional[str] = Field(None, description="Mandatory if decision is REJECT")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_decision(self) -> "BookingDecisionRequest":
        dec = self.decision.strip().upper()
        if dec not in ("ACCEPT", "REJECT"):
            raise ValueError("decision must be either 'ACCEPT' or 'REJECT'")
        self.decision = dec
        if dec == "REJECT" and (not self.rejection_reason or not self.rejection_reason.strip()):
            raise ValueError("rejection_reason is required when rejecting a reservation")
        return self


class BookingDriverAssignRequest(BaseModel):
    """Payload to assign a commercial driver to a WITH_DRIVER booking."""

    driver_id: UUID = Field(..., description="User ID of verified commercial driver")

    model_config = ConfigDict(extra="forbid")


class BookingCancelRequest(BaseModel):
    """Cancellation request payload before trip execution."""

    cancellation_reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")

    model_config = ConfigDict(extra="forbid")


class BookingStartTripRequest(BaseModel):
    """Odometer and timestamp recording payload when vehicle is handed over."""

    start_odometer: int = Field(..., ge=0, description="Odometer reading at vehicle pickup (km)")

    model_config = ConfigDict(extra="forbid")


class BookingEndTripRequest(BaseModel):
    """Odometer and timestamp recording payload when vehicle is returned."""

    end_odometer: int = Field(..., ge=0, description="Odometer reading at vehicle return (km)")

    model_config = ConfigDict(extra="forbid")


class BookingCarSummary(BaseModel):
    """Embedded summary of vehicle specifications."""

    id: UUID
    brand: str
    model: str
    year: int
    registration_number: str
    city: str

    model_config = ConfigDict(from_attributes=True)


class BookingResponse(BaseModel):
    """Serialized booking representation."""

    id: UUID
    booking_code: str
    customer_id: UUID
    car_id: UUID
    driver_id: Optional[UUID] = None
    booking_type: BookingType
    rental_type: RentalType
    status: BookingStatus

    # Window
    start_time: datetime
    end_time: datetime
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None

    # Station
    pickup_location: str
    dropoff_location: str

    # Mileage
    start_odometer: Optional[int] = None
    end_odometer: Optional[int] = None

    # Immutable Pricing Snapshot
    base_amount: Decimal
    driver_charge: Decimal
    platform_fee: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    security_deposit: Decimal
    total_amount: Decimal
    currency: str = "INR"

    # Cancellation Metadata
    cancelled_at: Optional[datetime] = None
    cancelled_by_id: Optional[UUID] = None
    cancellation_reason: Optional[str] = None
    cancellation_fee: Decimal
    refund_amount: Decimal

    created_at: datetime
    updated_at: datetime

    # Embedded car summary
    car: Optional[BookingCarSummary] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBookingResponse(BaseModel):
    """Paginated collection of booking reservations."""

    items: List[BookingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
