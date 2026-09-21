"""Driver Profile Service.

Handles business rules, verification guards, and transactional logic for commercial drivers.
"""

from datetime import date, timedelta
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.enums import DriverVerificationStatus, DriverDutyStatus
from app.models.user import DriverProfile
from app.repositories.driver_repository import DriverRepository
from app.schemas.driver import DriverProfileResponse, DriverProfileUpdateRequest


class DriverService:
    """Service managing driver profile operations and duty status transitions."""

    def __init__(self, db: Session):
        self.db = db
        self.driver_repo = DriverRepository(db)

    def _ensure_driver_profile(self, user_id: UUID) -> DriverProfile:
        """Fetch existing driver profile or initialize a pending profile for the driver."""
        profile = self.driver_repo.get_by_user_id(user_id)
        if profile:
            return profile

        # Initialize profile with unverified pending status
        default_license = f"DL-{str(user_id).replace('-', '')[:12].upper()}"
        default_expiry = date.today() + timedelta(days=365 * 3)
        profile = self.driver_repo.create(
            user_id=user_id,
            license_number=default_license,
            license_expiry_date=default_expiry,
            experience_years=0,
        )
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_profile(self, user_id: UUID) -> DriverProfileResponse:
        """Fetch driver profile for authenticated driver."""
        profile = self._ensure_driver_profile(user_id)
        return DriverProfileResponse.model_validate(profile)

    def update_profile(
        self,
        user_id: UUID,
        request: DriverProfileUpdateRequest,
    ) -> DriverProfileResponse:
        """Partially update driver profile attributes.

        Enforces operational business rules:
        1. Drivers cannot self-verify ('verification_status' is excluded from request schema).
        2. Unverified drivers (not APPROVED) are forbidden from setting duty_status to ONLINE or ON_TRIP.
        3. Experience years must be non-negative.
        """
        profile = self._ensure_driver_profile(user_id)
        update_data = request.model_dump(exclude_unset=True)

        if not update_data:
            return DriverProfileResponse.model_validate(profile)

        # Duty status transition guard
        new_duty = update_data.get("duty_status")
        if new_duty and new_duty in (DriverDutyStatus.ONLINE, DriverDutyStatus.ON_TRIP):
            if profile.verification_status != DriverVerificationStatus.APPROVED.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unverified drivers cannot go ONLINE. Verification by an administrator is required.",
                )

        try:
            updated = self.driver_repo.update(profile, update_data)
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise

        return DriverProfileResponse.model_validate(updated)
