"""Customer Profile Repository.

Handles database operations for CustomerProfile entities.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import CustomerProfile


class CustomerRepository:
    """Repository handling CustomerProfile persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Optional[CustomerProfile]:
        """Fetch customer profile by user ID."""
        stmt = select(CustomerProfile).where(CustomerProfile.user_id == user_id)
        return self.db.scalars(stmt).first()

    def get_by_license_number(self, license_number: str) -> Optional[CustomerProfile]:
        """Fetch customer profile by driving license number."""
        stmt = select(CustomerProfile).where(
            CustomerProfile.driving_license_number == license_number.strip()
        )
        return self.db.scalars(stmt).first()

    def create_or_get(self, user_id: UUID) -> CustomerProfile:
        """Fetch existing customer profile or create an empty one."""
        existing = self.get_by_user_id(user_id)
        if existing:
            return existing

        profile = CustomerProfile(user_id=user_id)
        self.db.add(profile)
        self.db.flush()
        return profile

    def update(self, profile: CustomerProfile, update_data: dict) -> CustomerProfile:
        """Update mutable fields on a customer profile."""
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        self.db.flush()
        return profile
