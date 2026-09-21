"""Owner Profile Pydantic Schemas.

Defines schemas for vehicle fleet owners.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OwnerProfileResponse(BaseModel):
    """Owner profile response schema.

    Returns safe business and mock payout reference info. Never exposes sensitive financial credentials.
    """

    id: UUID
    user_id: UUID
    business_name: Optional[str] = None
    tax_id_number: Optional[str] = None
    payout_account_reference: Optional[str] = None
    payout_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnerProfileUpdateRequest(BaseModel):
    """Schema for updating vehicle owner profile.

    Allows updating business identity and payout reference tokens.
    Sensitive credentials (CVV, passwords, full account numbers) are not accepted.
    """

    business_name: Optional[str] = Field(
        None,
        max_length=150,
        description="Registered business / fleet operator name",
    )
    tax_id_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Official tax identification / GSTIN / PAN number",
    )
    payout_account_reference: Optional[str] = Field(
        None,
        max_length=100,
        description="Non-sensitive payout reference token (e.g., mock_payout_ref_123)",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("business_name", "tax_id_number", "payout_account_reference")
    @classmethod
    def clean_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None
