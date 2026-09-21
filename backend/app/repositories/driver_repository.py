"""Driver Profile Repository.

Handles database operations for DriverProfile entities.
"""

from datetime import date
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.enums import DriverVerificationStatus, DriverDutyStatus
from app.models.user import DriverProfile


class DriverRepository:
    """Repository handling DriverProfile persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Optional[DriverProfile]:
        """Fetch driver profile by user ID."""
        stmt = select(DriverProfile).where(DriverProfile.user_id == user_id)
        return self.db.scalars(stmt).first()

    def get_by_license_number(self, license_number: str) -> Optional[DriverProfile]:
        """Fetch driver profile by commercial license number."""
        stmt = select(DriverProfile).where(
            DriverProfile.license_number == license_number.strip()
        )
        return self.db.scalars(stmt).first()

    def create(
        self,
        user_id: UUID,
        license_number: str,
        license_expiry_date: date,
        experience_years: int = 0,
        current_city: Optional[str] = None,
    ) -> DriverProfile:
        """Create a new driver profile."""
        profile = DriverProfile(
            user_id=user_id,
            license_number=license_number.strip(),
            license_expiry_date=license_expiry_date,
            experience_years=experience_years,
            verification_status=DriverVerificationStatus.PENDING.value,
            duty_status=DriverDutyStatus.OFFLINE.value,
            current_city=current_city.strip() if current_city else None,
        )
        self.db.add(profile)
        self.db.flush()
        return profile

    def update(self, profile: DriverProfile, update_data: dict) -> DriverProfile:
        """Update mutable fields on a driver profile."""
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        self.db.flush()
        return profile
