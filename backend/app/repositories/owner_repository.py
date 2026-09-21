"""Owner Profile Repository.

Handles database operations for OwnerProfile entities.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import OwnerProfile


class OwnerRepository:
    """Repository handling OwnerProfile persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> Optional[OwnerProfile]:
        """Fetch owner profile by user ID."""
        stmt = select(OwnerProfile).where(OwnerProfile.user_id == user_id)
        return self.db.scalars(stmt).first()

    def create_or_get(self, user_id: UUID) -> OwnerProfile:
        """Fetch existing owner profile or initialize a new one."""
        existing = self.get_by_user_id(user_id)
        if existing:
            return existing

        profile = OwnerProfile(user_id=user_id)
        self.db.add(profile)
        self.db.flush()
        return profile

    def update(self, profile: OwnerProfile, update_data: dict) -> OwnerProfile:
        """Update mutable fields on an owner profile."""
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        self.db.flush()
        return profile
