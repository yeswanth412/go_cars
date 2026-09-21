"""Car Repository.

Encapsulates direct database queries, filters, pagination, and persistence for vehicle fleet entities.
"""

from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session, selectinload
from app.models.enums import CarStatus
from app.models.car import Car, CarImage, CarDocument, CarBlackoutPeriod
from app.models.booking import Booking


class CarRepository:
    """Repository managing Car persistence and query operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        owner_id: UUID,
        brand: str,
        model: str,
        year: int,
        registration_number: str,
        fuel_type: str,
        transmission: str,
        seating_capacity: int,
        odometer_km: int,
        rc_number: str,
        insurance_policy_number: str,
        insurance_expiry_date,
        city: str,
        address: str,
        hourly_rate: Decimal,
        daily_rate: Decimal,
        weekly_rate: Decimal,
        is_self_drive_allowed: bool = True,
        is_driver_allowed: bool = True,
        status: str = CarStatus.PENDING_APPROVAL.value,
    ) -> Car:
        """Create a new car record with PENDING_APPROVAL status."""
        car = Car(
            owner_id=owner_id,
            brand=brand.strip(),
            model=model.strip(),
            year=year,
            registration_number=registration_number.strip().upper(),
            fuel_type=fuel_type,
            transmission=transmission,
            seating_capacity=seating_capacity,
            odometer_km=odometer_km,
            rc_number=rc_number.strip(),
            insurance_policy_number=insurance_policy_number.strip(),
            insurance_expiry_date=insurance_expiry_date,
            city=city.strip(),
            address=address.strip(),
            hourly_rate=hourly_rate,
            daily_rate=daily_rate,
            weekly_rate=weekly_rate,
            is_self_drive_allowed=is_self_drive_allowed,
            is_driver_allowed=is_driver_allowed,
            status=status,
        )
        self.db.add(car)
        self.db.flush()
        return car

    def get_by_id(self, car_id: UUID) -> Optional[Car]:
        """Fetch car by primary key ID without relationship preloading."""
        stmt = select(Car).where(Car.id == car_id)
        return self.db.scalars(stmt).first()

    def get_by_id_with_relations(self, car_id: UUID) -> Optional[Car]:
        """Fetch car by ID eagerly loading images, documents, and blackout periods."""
        stmt = (
            select(Car)
            .options(
                selectinload(Car.images),
                selectinload(Car.documents),
                selectinload(Car.blackout_periods),
            )
            .where(Car.id == car_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_registration_number(self, registration_number: str) -> Optional[Car]:
        """Fetch car by unique registration plate number."""
        stmt = select(Car).where(Car.registration_number == registration_number.strip().upper())
        return self.db.scalars(stmt).first()

    def count_bookings(self, car_id: UUID) -> int:
        """Count total historical transactions (bookings and reviews) linked to this car.
        
        Ensures hard deletion checks all related records and never violates FK constraints.
        """
        from app.models.review import Review

        booking_count = self.db.scalar(select(func.count(Booking.id)).where(Booking.car_id == car_id)) or 0
        review_count = self.db.scalar(select(func.count(Review.id)).where(Review.car_id == car_id)) or 0
        return booking_count + review_count

    def is_car_available_for_window(self, car_id: UUID, start_time, end_time) -> Tuple[bool, Optional[str]]:
        """Verify vehicle availability considering status, blackout periods, and active bookings.
        
        Confirm AVAILABLE status alone is not sufficient:
        - Must have status == AVAILABLE
        - Must not overlap any scheduled blackout period
        - Must not overlap any active booking (PENDING_PAYMENT, CONFIRMED, IN_PROGRESS)
        """
        from app.models.enums import BookingStatus

        car = self.get_by_id(car_id)
        if not car:
            return False, "Car not found"
        if car.status != CarStatus.AVAILABLE.value:
            return False, f"Car is not in AVAILABLE status (current: {car.status})"

        # Check blackout period overlap
        blackout_conflict = self.db.scalars(
            select(CarBlackoutPeriod).where(
                CarBlackoutPeriod.car_id == car_id,
                CarBlackoutPeriod.start_time < end_time,
                CarBlackoutPeriod.end_time > start_time,
            )
        ).first()
        if blackout_conflict:
            return False, "Car is scheduled for maintenance or blackout period during this window"

        # Check existing active bookings overlap
        active_statuses = [
            BookingStatus.PENDING_PAYMENT.value,
            BookingStatus.CONFIRMED.value,
            BookingStatus.IN_PROGRESS.value,
        ]
        booking_conflict = self.db.scalars(
            select(Booking).where(
                Booking.car_id == car_id,
                Booking.status.in_(active_statuses),
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
        ).first()
        if booking_conflict:
            return False, "Car already has a conflicting reservation during this window"

        return True, None

    def list_by_owner(
        self,
        owner_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Car], int]:
        """List cars belonging to a specific owner with optional status filter."""
        base_query = (
            select(Car)
            .options(
                selectinload(Car.images),
                selectinload(Car.documents),
                selectinload(Car.blackout_periods),
            )
            .where(Car.owner_id == owner_id)
        )

        if status:
            base_query = base_query.where(Car.status == status)

        count_query = select(func.count(Car.id)).where(Car.owner_id == owner_id)
        if status:
            count_query = count_query.where(Car.status == status)

        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * page_size
        stmt = base_query.order_by(Car.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())

        return items, total

    def list_all_admin(
        self,
        status: Optional[str] = None,
        city: Optional[str] = None,
        brand: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Car], int]:
        """Administrative query across all platform vehicles with multi-field filtering."""
        base_query = (
            select(Car)
            .options(
                selectinload(Car.images),
                selectinload(Car.documents),
                selectinload(Car.blackout_periods),
            )
        )

        conditions = []
        if status:
            conditions.append(Car.status == status)
        if city:
            conditions.append(Car.city.ilike(f"%{city.strip()}%"))
        if brand:
            conditions.append(Car.brand.ilike(f"%{brand.strip()}%"))
        if owner_id:
            conditions.append(Car.owner_id == owner_id)

        if conditions:
            base_query = base_query.where(and_(*conditions))

        count_query = select(func.count(Car.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * page_size
        stmt = base_query.order_by(Car.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())

        return items, total

    def search_public(
        self,
        city: Optional[str] = None,
        fuel_type: Optional[str] = None,
        transmission: Optional[str] = None,
        min_seats: Optional[int] = None,
        is_self_drive_allowed: Optional[bool] = None,
        is_driver_allowed: Optional[bool] = None,
        min_daily_rate: Optional[Decimal] = None,
        max_daily_rate: Optional[Decimal] = None,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Car], int]:
        """Public car discovery query.

        MANDATORY RULE: ONLY cars with status == AVAILABLE are returned.
        Pending, maintenance, suspended, or inactive cars are strictly excluded.
        """
        base_query = (
            select(Car)
            .options(selectinload(Car.images))
            .where(Car.status == CarStatus.AVAILABLE.value)
        )

        conditions = []
        if city:
            conditions.append(Car.city.ilike(f"%{city.strip()}%"))
        if fuel_type:
            conditions.append(Car.fuel_type == fuel_type)
        if transmission:
            conditions.append(Car.transmission == transmission)
        if min_seats:
            conditions.append(Car.seating_capacity >= min_seats)
        if is_self_drive_allowed is not None:
            conditions.append(Car.is_self_drive_allowed == is_self_drive_allowed)
        if is_driver_allowed is not None:
            conditions.append(Car.is_driver_allowed == is_driver_allowed)
        if min_daily_rate is not None:
            conditions.append(Car.daily_rate >= min_daily_rate)
        if max_daily_rate is not None:
            conditions.append(Car.daily_rate <= max_daily_rate)
        if brand:
            conditions.append(Car.brand.ilike(f"%{brand.strip()}%"))
        if model:
            conditions.append(Car.model.ilike(f"%{model.strip()}%"))

        if conditions:
            base_query = base_query.where(and_(*conditions))

        count_query = select(func.count(Car.id)).where(Car.status == CarStatus.AVAILABLE.value)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total = self.db.scalar(count_query) or 0

        offset = (page - 1) * page_size
        stmt = base_query.order_by(Car.daily_rate.asc(), Car.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())

        return items, total

    def update(self, car: Car, update_data: dict) -> Car:
        """Update mutable fields on a car entity."""
        for field, value in update_data.items():
            if hasattr(car, field):
                setattr(car, field, value)
        self.db.flush()
        return car

    def update_status(self, car: Car, status: str) -> Car:
        """Update operational status for a car."""
        car.status = status
        self.db.flush()
        return car

    def delete(self, car: Car) -> None:
        """Hard delete a car entity from database."""
        self.db.delete(car)
        self.db.flush()
