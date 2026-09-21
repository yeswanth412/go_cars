"""Car Fleet Management SQLAlchemy Models.

Defines:
- Car (core vehicle specifications, registration, and platform-controlled rates)
- CarImage (vehicle photo URLs and primary display image)
- CarDocument (registration certificates, insurance, and fitness compliance)
- CarBlackoutPeriod (scheduled maintenance & owner unavailability blocks)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    CarStatus,
    FuelType,
    TransmissionType,
    DocumentType,
    DocumentVerificationStatus,
    BlackoutReason,
)


class Car(Base):
    """Vehicle fleet record listed on GoCars."""

    __tablename__ = "cars"
    __table_args__ = (
        CheckConstraint("seating_capacity > 0", name="chk_car_seating_capacity_positive"),
        CheckConstraint("odometer_km >= 0", name="chk_car_odometer_non_negative"),
        CheckConstraint("hourly_rate >= 0", name="chk_car_hourly_rate_non_negative"),
        CheckConstraint("daily_rate >= 0", name="chk_car_daily_rate_non_negative"),
        CheckConstraint("weekly_rate >= 0", name="chk_car_weekly_rate_non_negative"),
        Index("ix_cars_city_status", "city", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    # Vehicle Specifications
    brand: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    registration_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )
    fuel_type: Mapped[str] = mapped_column(
        String(20),
        default=FuelType.PETROL.value,
        nullable=False,
    )
    transmission: Mapped[str] = mapped_column(
        String(20),
        default=TransmissionType.MANUAL.value,
        nullable=False,
    )
    seating_capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    odometer_km: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Compliance & Registration
    rc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    insurance_policy_number: Mapped[str] = mapped_column(String(50), nullable=False)
    insurance_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Operational status & Location
    status: Mapped[str] = mapped_column(
        String(25),
        default=CarStatus.PENDING_APPROVAL.value,
        index=True,
        nullable=False,
    )
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)

    # Platform-Controlled Pricing (Owners cannot modify these directly)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weekly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Supported booking modes
    is_self_drive_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_driver_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    owner: Mapped["User"] = relationship("User", back_populates="cars")  # noqa: F821
    images: Mapped[List["CarImage"]] = relationship(
        "CarImage",
        back_populates="car",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["CarDocument"]] = relationship(
        "CarDocument",
        back_populates="car",
        cascade="all, delete-orphan",
    )
    blackout_periods: Mapped[List["CarBlackoutPeriod"]] = relationship(
        "CarBlackoutPeriod",
        back_populates="car",
        cascade="all, delete-orphan",
    )
    bookings: Mapped[List["Booking"]] = relationship(  # noqa: F821
        "Booking",
        back_populates="car",
    )
    reviews: Mapped[List["Review"]] = relationship(  # noqa: F821
        "Review",
        back_populates="car",
    )


class CarImage(Base):
    """Exterior and interior vehicle photos."""

    __tablename__ = "car_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    car_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    car: Mapped["Car"] = relationship("Car", back_populates="images")


class CarDocument(Base):
    """Vehicle legal compliance documentation."""

    __tablename__ = "car_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    car_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(30),
        default=DocumentType.RC_BOOK.value,
        nullable=False,
    )
    document_url: Mapped[str] = mapped_column(String(500), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(20),
        default=DocumentVerificationStatus.PENDING.value,
        nullable=False,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    car: Mapped["Car"] = relationship("Car", back_populates="documents")


class CarBlackoutPeriod(Base):
    """Time windows during which a car is unavailable (e.g. maintenance, owner personal use)."""

    __tablename__ = "car_blackout_periods"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="chk_blackout_valid_time_window"),
        Index("ix_blackout_car_window", "car_id", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    car_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(50),
        default=BlackoutReason.MAINTENANCE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    car: Mapped["Car"] = relationship("Car", back_populates="blackout_periods")
