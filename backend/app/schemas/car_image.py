"""Car Image Pydantic Schemas.

Defines schemas for vehicle photo gallery management.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CarImageCreateRequest(BaseModel):
    """Schema for adding a vehicle photo reference."""

    image_url: str = Field(..., max_length=500, description="URL or CDN storage link of vehicle photo")
    is_primary: bool = Field(False, description="Flag indicating if this photo is the main display photo")
    caption: Optional[str] = Field(None, max_length=100, description="Optional photo caption (e.g. Front View)")

    model_config = ConfigDict(extra="forbid")

    @field_validator("image_url", "caption")
    @classmethod
    def clean_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None


class CarImageResponse(BaseModel):
    """Vehicle photo response representation."""

    id: UUID
    car_id: UUID
    image_url: str
    is_primary: bool
    caption: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
