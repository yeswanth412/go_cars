"""Booking Transaction SQLAlchemy Model.

Defines:
- Booking (central rental contract, vehicle reservations, immutable pricing snapshot, and state transitions)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    BookingType,
    RentalType,
    BookingStatus,
)


class Booking(Base):
    """Core transaction entity for all self-drive and with-driver car rentals."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="chk_booking_valid_time_window"),
        CheckConstraint("base_amount >= 0", name="chk_booking_base_amount_non_negative"),
        CheckConstraint("driver_charge >= 0", name="chk_booking_driver_charge_non_negative"),
        CheckConstraint("platform_fee >= 0", name="chk_booking_platform_fee_non_negative"),
        CheckConstraint("tax_amount >= 0", name="chk_booking_tax_amount_non_negative"),
        CheckConstraint("discount_amount >= 0", name="chk_booking_discount_amount_non_negative"),
        CheckConstraint("security_deposit >= 0", name="chk_booking_security_deposit_non_negative"),
        CheckConstraint("total_amount >= 0", name="chk_booking_total_amount_non_negative"),
        CheckConstraint("cancellation_fee >= 0", name="chk_booking_cancellation_fee_non_negative"),
        CheckConstraint("refund_amount >= 0", name="chk_booking_refund_amount_non_negative"),
        Index("ix_bookings_car_window_status", "car_id", "start_time", "end_time", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    booking_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    # Actor References
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    car_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Rental Configuration
    booking_type: Mapped[str] = mapped_column(
        String(20),
        default=BookingType.SELF_DRIVE.value,
        nullable=False,
    )
    rental_type: Mapped[str] = mapped_column(
        String(20),
        default=RentalType.DAILY.value,
        nullable=False,
    )

    # Schedule & Actual Journey
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    actual_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Station / Address
    pickup_location: Mapped[str] = mapped_column(Text, nullable=False)
    dropoff_location: Mapped[str] = mapped_column(Text, nullable=False)

    # Trip Mileage
    start_odometer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_odometer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Booking Lifecycle Status
    status: Mapped[str] = mapped_column(
        String(25),
        default=BookingStatus.PENDING_PAYMENT.value,
        index=True,
        nullable=False,
    )

    # =========================================================================
    # Immutable Pricing Snapshot (Frozen at booking confirmation)
    # =========================================================================
    base_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    driver_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # =========================================================================
    # Cancellation & Refund Management
    # =========================================================================
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped["User"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[customer_id],
        back_populates="customer_bookings",
    )
    car: Mapped["Car"] = relationship(  # noqa: F821
        "Car",
        back_populates="bookings",
    )
    driver: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User",
        foreign_keys=[driver_id],
        back_populates="driver_bookings",
    )
    cancelled_by: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User",
        foreign_keys=[cancelled_by_id],
    )
    # 1 Booking -> Many Payments (allows retries, refunds, and adjustments)
    payments: Mapped[List["Payment"]] = relationship(  # noqa: F821
        "Payment",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
    # 1 Booking -> 1 Review (optional, submitted after trip completion)
    review: Mapped[Optional["Review"]] = relationship(  # noqa: F821
        "Review",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
    )
