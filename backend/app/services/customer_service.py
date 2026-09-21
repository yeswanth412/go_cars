"""Customer Profile Service.

Handles business rules and transactional logic for customer profiles.
"""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerProfileResponse, CustomerProfileUpdateRequest


class CustomerService:
    """Service managing customer profile domain logic."""

    def __init__(self, db: Session):
        self.db = db
        self.customer_repo = CustomerRepository(db)

    def get_profile(self, user_id: UUID) -> CustomerProfileResponse:
        """Fetch or initialize customer profile for the user."""
        profile = self.customer_repo.create_or_get(user_id)
        self.db.commit()
        return CustomerProfileResponse.model_validate(profile)

    def update_profile(
        self,
        user_id: UUID,
        request: CustomerProfileUpdateRequest,
    ) -> CustomerProfileResponse:
        """Partially update customer profile.

        Validates driving license number uniqueness if updated.
        Self-verification is strictly prohibited and excluded from request schemas.

        Raises:
            HTTPException: 409 Conflict if driving license is already linked to another customer.
        """
        profile = self.customer_repo.create_or_get(user_id)
        update_data = request.model_dump(exclude_unset=True)

        if not update_data:
            return CustomerProfileResponse.model_validate(profile)

        license_num = update_data.get("driving_license_number")
        if license_num and license_num != profile.driving_license_number:
            existing_license = self.customer_repo.get_by_license_number(license_num)
            if existing_license and existing_license.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Driving license number is already registered to another user",
                )

        try:
            updated = self.customer_repo.update(profile, update_data)
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise

        return CustomerProfileResponse.model_validate(updated)
