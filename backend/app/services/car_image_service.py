"""Car Image Service.

Handles vehicle photo uploads, ownership verification, and gallery management.
"""

from typing import List
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.car_repository import CarRepository
from app.repositories.car_image_repository import CarImageRepository
from app.schemas.car_image import CarImageCreateRequest, CarImageResponse


class CarImageService:
    """Service managing vehicle photos with ownership-based authorization."""

    def __init__(self, db: Session):
        self.db = db
        self.car_repo = CarRepository(db)
        self.image_repo = CarImageRepository(db)

    def _verify_car_ownership(self, car_id: UUID, owner_id: UUID):
        """Ensure car exists and is owned by caller."""
        car = self.car_repo.get_by_id(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        if car.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage images for this vehicle",
            )
        return car

    def add_image(
        self,
        car_id: UUID,
        owner_id: UUID,
        request: CarImageCreateRequest,
    ) -> CarImageResponse:
        """Add image reference to an owned vehicle."""
        self._verify_car_ownership(car_id, owner_id)

        try:
            image = self.image_repo.create(
                car_id=car_id,
                image_url=request.image_url,
                is_primary=request.is_primary,
                caption=request.caption,
            )
            self.db.commit()
            self.db.refresh(image)
        except Exception:
            self.db.rollback()
            raise

        return CarImageResponse.model_validate(image)

    def list_images(self, car_id: UUID, owner_id: UUID) -> List[CarImageResponse]:
        """List all photos for an owned vehicle."""
        self._verify_car_ownership(car_id, owner_id)
        images = self.image_repo.list_by_car_id(car_id)
        return [CarImageResponse.model_validate(img) for img in images]

    def delete_image(self, image_id: UUID, owner_id: UUID) -> None:
        """Delete an image record for an owned vehicle."""
        image = self.image_repo.get_by_id(image_id)
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found",
            )
        self._verify_car_ownership(image.car_id, owner_id)

        try:
            self.image_repo.delete(image)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
