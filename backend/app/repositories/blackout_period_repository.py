"""Car Blackout Period Repository.

Handles persistence and overlap queries for vehicle unavailability intervals.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.models.car import CarBlackoutPeriod


class BlackoutPeriodRepository:
    """Repository managing CarBlackoutPeriod database operations."""

    def __init__(self, db: Session):
        self.db = db

    def has_overlap(
        self,
        car_id: UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Check whether a requested time interval overlaps with any existing blackout window.

        Two intervals [A, B] and [C, D] overlap if A < D and B > C.
        """
        conditions = [
            CarBlackoutPeriod.car_id == car_id,
            CarBlackoutPeriod.start_time < end_time,
            CarBlackoutPeriod.end_time > start_time,
        ]
        if exclude_id:
            conditions.append(CarBlackoutPeriod.id != exclude_id)

        stmt = select(CarBlackoutPeriod).where(and_(*conditions))
        return self.db.scalars(stmt).first() is not None

    def create(
        self,
        car_id: UUID,
        start_time: datetime,
        end_time: datetime,
        reason: str,
    ) -> CarBlackoutPeriod:
        """Persist a new blackout interval."""
        blackout = CarBlackoutPeriod(
            car_id=car_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
        )
        self.db.add(blackout)
        self.db.flush()
        return blackout

    def get_by_id(self, blackout_id: UUID) -> Optional[CarBlackoutPeriod]:
        """Fetch blackout period by primary key ID."""
        stmt = select(CarBlackoutPeriod).where(CarBlackoutPeriod.id == blackout_id)
        return self.db.scalars(stmt).first()

    def list_by_car_id(self, car_id: UUID) -> List[CarBlackoutPeriod]:
        """List all scheduled blackout periods for a car ordered chronologically."""
        stmt = (
            select(CarBlackoutPeriod)
            .where(CarBlackoutPeriod.car_id == car_id)
            .order_by(CarBlackoutPeriod.start_time.asc())
        )
        return list(self.db.scalars(stmt).all())

    def delete(self, blackout: CarBlackoutPeriod) -> None:
        """Remove a blackout interval from database."""
        self.db.delete(blackout)
        self.db.flush()
