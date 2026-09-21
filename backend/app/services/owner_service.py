"""Owner Profile Service.

Handles business rules and transactional logic for fleet owners.
"""

from uuid import UUID
from sqlalchemy.orm import Session
from app.repositories.owner_repository import OwnerRepository
from app.schemas.owner import OwnerProfileResponse, OwnerProfileUpdateRequest


class OwnerService:
    """Service managing vehicle owner profile domain logic."""

    def __init__(self, db: Session):
        self.db = db
        self.owner_repo = OwnerRepository(db)

    def get_profile(self, user_id: UUID) -> OwnerProfileResponse:
        """Fetch or initialize owner profile for the user."""
        profile = self.owner_repo.create_or_get(user_id)
        self.db.commit()
        return OwnerProfileResponse.model_validate(profile)

    def update_profile(
        self,
        user_id: UUID,
        request: OwnerProfileUpdateRequest,
    ) -> OwnerProfileResponse:
        """Partially update owner business identity and payout reference.

        Never accepts or persists raw financial credentials.
        """
        profile = self.owner_repo.create_or_get(user_id)
        update_data = request.model_dump(exclude_unset=True)

        if not update_data:
            return OwnerProfileResponse.model_validate(profile)

        try:
            updated = self.owner_repo.update(profile, update_data)
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise

        return OwnerProfileResponse.model_validate(updated)
