"""Car Blackout Period Schemas.

Defines schemas for scheduling vehicle unavailability intervals (maintenance, personal use).
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.enums import BlackoutReason


class BlackoutPeriodCreateRequest(BaseModel):
    """Schema for scheduling a vehicle blackout window."""

    start_time: datetime = Field(
        ...,
        description="Window start timestamp (must be timezone-aware UTC)",
    )
    end_time: datetime = Field(
        ...,
        description="Window end timestamp (must be timezone-aware UTC, after start_time)",
    )
    reason: BlackoutReason = Field(
        BlackoutReason.MAINTENANCE,
        description="Reason for unavailability (MAINTENANCE, OWNER_USE, LEGAL_INSPECTION, OTHER)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_window(self) -> "BlackoutPeriodCreateRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class BlackoutPeriodResponse(BaseModel):
    """Vehicle blackout interval representation."""

    id: UUID
    car_id: UUID
    start_time: datetime
    end_time: datetime
    reason: BlackoutReason
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
