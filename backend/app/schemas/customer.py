"""Customer Profile Pydantic Schemas.

Defines schemas for customer profile management and self-service updates.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerProfileResponse(BaseModel):
    """Customer profile response schema."""

    id: UUID
    user_id: UUID
    driving_license_number: Optional[str] = None
    license_expiry_date: Optional[date] = None
    license_image_url: Optional[str] = None
    is_license_verified: bool
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerProfileUpdateRequest(BaseModel):
    """Schema for customer profile update.

    Customers can submit license and emergency contact info.
    Self-verification ('is_license_verified') is strictly disallowed and excluded.
    """

    driving_license_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Official driving license number",
    )
    license_expiry_date: Optional[date] = Field(
        None,
        description="Driving license expiration date",
    )
    license_image_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Link to uploaded driving license image",
    )
    emergency_contact_name: Optional[str] = Field(
        None,
        max_length=150,
        description="Emergency contact person full name",
    )
    emergency_contact_phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Emergency contact phone number",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("driving_license_number", "license_image_url", "emergency_contact_name", "emergency_contact_phone")
    @classmethod
    def clean_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None
