"""User Profile Pydantic Schemas.

Defines request and response schemas for general user profile management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserProfileResponse(BaseModel):
    """Safe public user profile schema.

    Never exposes password hashes or internal sensitive data.
    """

    id: UUID
    full_name: str
    email: str
    phone_number: str
    is_active: bool
    is_verified: bool
    roles: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateRequest(BaseModel):
    """Schema for updating authenticated user profile.

    Only allows updating non-sensitive mutable attributes: full_name and phone_number.
    Protected attributes (id, email, password, roles, is_active, is_verified) are strictly excluded.
    """

    full_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=150,
        description="Legal full name",
    )
    phone_number: Optional[str] = Field(
        None,
        min_length=7,
        max_length=20,
        description="Contact phone number",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip()
            if len(v_clean) < 2:
                raise ValueError("Full name cannot be blank or shorter than 2 characters")
            return v_clean
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip()
            if len(v_clean) < 7:
                raise ValueError("Phone number must be at least 7 characters")
            return v_clean
        return v
