"""Driver Profile Pydantic Schemas.

Defines schemas for commercial drivers.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import DriverVerificationStatus, DriverDutyStatus


class DriverProfileResponse(BaseModel):
    """Driver profile response schema."""

    id: UUID
    user_id: UUID
    license_number: str
    license_expiry_date: date
    experience_years: int
    verification_status: DriverVerificationStatus
    duty_status: DriverDutyStatus
    current_city: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverProfileUpdateRequest(BaseModel):
    """Schema for driver profile updates.

    Drivers can update their operating city, experience, and duty status.
    Self-verification ('verification_status') is strictly excluded.
    """

    experience_years: Optional[int] = Field(
        None,
        ge=0,
        description="Years of professional driving experience (>= 0)",
    )
    duty_status: Optional[DriverDutyStatus] = Field(
        None,
        description="Driver operational availability status (OFFLINE, ONLINE, ON_TRIP)",
    )
    current_city: Optional[str] = Field(
        None,
        max_length=100,
        description="Operating city",
    )
    license_expiry_date: Optional[date] = Field(
        None,
        description="Updated driving license expiry date",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("current_city")
    @classmethod
    def clean_city(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None
