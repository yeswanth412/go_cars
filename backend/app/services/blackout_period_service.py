"""Car Blackout Period Service.

Handles scheduling, overlap prevention, and lifecycle of vehicle unavailability intervals.
"""

from typing import List
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.car_repository import CarRepository
from app.repositories.blackout_period_repository import BlackoutPeriodRepository
from app.schemas.blackout_period import BlackoutPeriodCreateRequest, BlackoutPeriodResponse


class BlackoutPeriodService:
    """Service managing vehicle unavailability windows."""

    def __init__(self, db: Session):
        self.db = db
        self.car_repo = CarRepository(db)
        self.blackout_repo = BlackoutPeriodRepository(db)

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
                detail="You do not have permission to manage blackout periods for this vehicle",
            )
        return car

    def create_blackout(
        self,
        car_id: UUID,
        owner_id: UUID,
        request: BlackoutPeriodCreateRequest,
    ) -> BlackoutPeriodResponse:
        """Schedule a new blackout interval with overlap validation."""
        self._verify_car_ownership(car_id, owner_id)

        # Check for overlapping blackout periods
        if self.blackout_repo.has_overlap(car_id, request.start_time, request.end_time):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requested blackout window overlaps with an existing scheduled period",
            )

        try:
            blackout = self.blackout_repo.create(
                car_id=car_id,
                start_time=request.start_time,
                end_time=request.end_time,
                reason=request.reason.value,
            )
            self.db.commit()
            self.db.refresh(blackout)
        except Exception:
            self.db.rollback()
            raise

        return BlackoutPeriodResponse.model_validate(blackout)

    def list_blackouts(self, car_id: UUID, owner_id: UUID) -> List[BlackoutPeriodResponse]:
        """List scheduled blackout periods for an owned vehicle."""
        self._verify_car_ownership(car_id, owner_id)
        periods = self.blackout_repo.list_by_car_id(car_id)
        return [BlackoutPeriodResponse.model_validate(p) for p in periods]

    def delete_blackout(self, blackout_id: UUID, owner_id: UUID) -> None:
        """Remove a scheduled blackout interval."""
        blackout = self.blackout_repo.get_by_id(blackout_id)
        if not blackout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blackout period not found",
            )
        self._verify_car_ownership(blackout.car_id, owner_id)

        try:
            self.blackout_repo.delete(blackout)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
