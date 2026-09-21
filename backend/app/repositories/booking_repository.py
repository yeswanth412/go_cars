"""Booking Repository.

Encapsulates database persistence, concurrency queries, relationship loading,
and filtering for Booking entities.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID
import uuid
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload
from app.models.booking import Booking
from app.models.car import Car
from app.models.enums import BookingStatus


class BookingRepository:
    """Repository managing Booking database operations."""

    def __init__(self, db: Session):
        self.db = db

    def generate_booking_code(self) -> str:
        """Generate human-readable, unique booking code."""
        suffix = str(uuid.uuid4())[:8].upper()
        return f"BK-{suffix}"

    def create(
        self,
        customer_id: UUID,
        car_id: UUID,
        booking_type: str,
        rental_type: str,
        start_time: datetime,
        end_time: datetime,
        pickup_location: str,
        dropoff_location: str,
        base_amount: Decimal,
        driver_charge: Decimal,
        platform_fee: Decimal,
        tax_amount: Decimal,
        security_deposit: Decimal,
        total_amount: Decimal,
        driver_id: Optional[UUID] = None,
        status: str = BookingStatus.PENDING_PAYMENT.value,
        discount_amount: Decimal = Decimal("0.00"),
        currency: str = "INR",
    ) -> Booking:
        """Persist a new booking entity with frozen pricing snapshot."""
        booking = Booking(
            booking_code=self.generate_booking_code(),
            customer_id=customer_id,
            car_id=car_id,
            driver_id=driver_id,
            booking_type=booking_type,
            rental_type=rental_type,
            start_time=start_time,
            end_time=end_time,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            status=status,
            base_amount=base_amount,
            driver_charge=driver_charge,
            platform_fee=platform_fee,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            security_deposit=security_deposit,
            total_amount=total_amount,
            currency=currency,
        )
        self.db.add(booking)
        self.db.flush()
        return booking

    def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        """Fetch booking by primary key."""
        stmt = select(Booking).where(Booking.id == booking_id)
        return self.db.scalars(stmt).first()

    def get_by_id_with_relations(self, booking_id: UUID) -> Optional[Booking]:
        """Fetch booking eager loading car, customer, and driver."""
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.car),
                selectinload(Booking.customer),
                selectinload(Booking.driver),
            )
            .where(Booking.id == booking_id)
        )
        return self.db.scalars(stmt).first()

    def check_car_overlap(
        self,
        car_id: UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_booking_id: Optional[UUID] = None,
    ) -> bool:
        """Check if car has active overlapping bookings.

        Active statuses that reserve vehicle availability:
        - PENDING_PAYMENT
        - CONFIRMED
        - IN_PROGRESS
        """
        active_statuses = [
            BookingStatus.PENDING_PAYMENT.value,
            BookingStatus.CONFIRMED.value,
            BookingStatus.IN_PROGRESS.value,
        ]
        conditions = [
            Booking.car_id == car_id,
            Booking.status.in_(active_statuses),
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        ]
        if exclude_booking_id:
            conditions.append(Booking.id != exclude_booking_id)

        stmt = select(Booking.id).where(and_(*conditions))
        return self.db.scalars(stmt).first() is not None

    def check_driver_overlap(
        self,
        driver_id: UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_booking_id: Optional[UUID] = None,
    ) -> bool:
        """Check if driver has active overlapping trip assignments."""
        active_statuses = [
            BookingStatus.PENDING_PAYMENT.value,
            BookingStatus.CONFIRMED.value,
            BookingStatus.IN_PROGRESS.value,
        ]
        conditions = [
            Booking.driver_id == driver_id,
            Booking.status.in_(active_statuses),
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        ]
        if exclude_booking_id:
            conditions.append(Booking.id != exclude_booking_id)

        stmt = select(Booking.id).where(and_(*conditions))
        return self.db.scalars(stmt).first() is not None

    def list_by_customer(
        self,
        customer_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Booking], int]:
        """Paginated query for customer bookings."""
        base_query = (
            select(Booking)
            .options(selectinload(Booking.car))
            .where(Booking.customer_id == customer_id)
        )
        if status:
            base_query = base_query.where(Booking.status == status.strip().upper())

        count_stmt = select(func.count(Booking.id)).where(Booking.customer_id == customer_id)
        if status:
            count_stmt = count_stmt.where(Booking.status == status.strip().upper())
        total = self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        stmt = base_query.order_by(Booking.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def list_by_owner(
        self,
        owner_id: UUID,
        status: Optional[str] = None,
        car_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Booking], int]:
        """Paginated query for bookings across an owner's vehicle fleet."""
        base_query = (
            select(Booking)
            .join(Car, Booking.car_id == Car.id)
            .options(selectinload(Booking.car))
            .where(Car.owner_id == owner_id)
        )
        count_stmt = (
            select(func.count(Booking.id))
            .join(Car, Booking.car_id == Car.id)
            .where(Car.owner_id == owner_id)
        )

        if status:
            base_query = base_query.where(Booking.status == status.strip().upper())
            count_stmt = count_stmt.where(Booking.status == status.strip().upper())
        if car_id:
            base_query = base_query.where(Booking.car_id == car_id)
            count_stmt = count_stmt.where(Booking.car_id == car_id)

        total = self.db.scalar(count_stmt) or 0
        offset = (page - 1) * page_size
        stmt = base_query.order_by(Booking.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def list_by_driver(
        self,
        driver_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Booking], int]:
        """Paginated query for driver trip assignments."""
        base_query = (
            select(Booking)
            .options(selectinload(Booking.car))
            .where(Booking.driver_id == driver_id)
        )
        count_stmt = select(func.count(Booking.id)).where(Booking.driver_id == driver_id)

        if status:
            base_query = base_query.where(Booking.status == status.strip().upper())
            count_stmt = count_stmt.where(Booking.status == status.strip().upper())

        total = self.db.scalar(count_stmt) or 0
        offset = (page - 1) * page_size
        stmt = base_query.order_by(Booking.start_time.asc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def list_all_admin(
        self,
        status: Optional[str] = None,
        car_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        driver_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Booking], int]:
        """Administrative query listing all platform bookings."""
        base_query = select(Booking).options(selectinload(Booking.car))
        count_stmt = select(func.count(Booking.id))

        conditions = []
        if status:
            conditions.append(Booking.status == status.strip().upper())
        if car_id:
            conditions.append(Booking.car_id == car_id)
        if customer_id:
            conditions.append(Booking.customer_id == customer_id)
        if driver_id:
            conditions.append(Booking.driver_id == driver_id)

        if conditions:
            base_query = base_query.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        total = self.db.scalar(count_stmt) or 0
        offset = (page - 1) * page_size
        stmt = base_query.order_by(Booking.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def update_status(self, booking: Booking, status: str) -> Booking:
        """Update booking lifecycle status."""
        booking.status = status
        self.db.flush()
        return booking

    def assign_driver(self, booking: Booking, driver_id: UUID) -> Booking:
        """Assign verified commercial driver to booking."""
        booking.driver_id = driver_id
        self.db.flush()
        return booking

    def record_trip_start(
        self,
        booking: Booking,
        start_odometer: int,
        actual_start_time: datetime,
    ) -> Booking:
        """Record trip start details."""
        booking.status = BookingStatus.IN_PROGRESS.value
        booking.start_odometer = start_odometer
        booking.actual_start_time = actual_start_time
        self.db.flush()
        return booking

    def record_trip_end(
        self,
        booking: Booking,
        end_odometer: int,
        actual_end_time: datetime,
    ) -> Booking:
        """Record trip completion details."""
        booking.status = BookingStatus.COMPLETED.value
        booking.end_odometer = end_odometer
        booking.actual_end_time = actual_end_time
        self.db.flush()
        return booking

    def record_cancellation(
        self,
        booking: Booking,
        cancelled_by_id: UUID,
        reason: Optional[str] = None,
        fee: Decimal = Decimal("0.00"),
        refund: Decimal = Decimal("0.00"),
    ) -> Booking:
        """Record booking cancellation."""
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancelled_by_id = cancelled_by_id
        booking.cancellation_reason = reason
        booking.cancellation_fee = fee
        booking.refund_amount = refund
        self.db.flush()
        return booking
