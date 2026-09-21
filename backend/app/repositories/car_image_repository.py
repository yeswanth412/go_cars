"""Car Image Repository.

Handles database queries and persistence for vehicle photos.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.car import CarImage


class CarImageRepository:
    """Repository managing CarImage database operations."""

    def __init__(self, db: Session):
        self.db = db

    def clear_primary(self, car_id: UUID) -> None:
        """Reset primary photo flag for all images of a car."""
        stmt = (
            update(CarImage)
            .where(CarImage.car_id == car_id)
            .values(is_primary=False)
        )
        self.db.execute(stmt)
        self.db.flush()

    def create(
        self,
        car_id: UUID,
        image_url: str,
        is_primary: bool = False,
        caption: Optional[str] = None,
    ) -> CarImage:
        """Persist a new car image."""
        if is_primary:
            self.clear_primary(car_id)

        image = CarImage(
            car_id=car_id,
            image_url=image_url,
            is_primary=is_primary,
            caption=caption,
        )
        self.db.add(image)
        self.db.flush()
        return image

    def get_by_id(self, image_id: UUID) -> Optional[CarImage]:
        """Fetch car image by primary key ID."""
        stmt = select(CarImage).where(CarImage.id == image_id)
        return self.db.scalars(stmt).first()

    def list_by_car_id(self, car_id: UUID) -> List[CarImage]:
        """List all images belonging to a specific car ordered by primary first."""
        stmt = (
            select(CarImage)
            .where(CarImage.car_id == car_id)
            .order_by(CarImage.is_primary.desc(), CarImage.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def delete(self, image: CarImage) -> None:
        """Delete an image record from database."""
        self.db.delete(image)
        self.db.flush()
