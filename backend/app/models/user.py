"""User, Role, and Profile SQLAlchemy Models.

Defines:
- User (core authentication & identity)
- Role (system roles: ADMIN, CUSTOMER, OWNER, DRIVER)
- UserRole (many-to-many junction table)
- CustomerProfile (self-drive & customer details)
- OwnerProfile (fleet owner info & mock payout reference)
- DriverProfile (commercial driver license, verification & duty status)
"""

import uuid
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Boolean,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    RoleName,
    DriverVerificationStatus,
    DriverDutyStatus,
)


class User(Base):
    """Core user account record for all actors on GoCars."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
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
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
    )
    user_roles: Mapped[List["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="roles",
    )
    customer_profile: Mapped[Optional["CustomerProfile"]] = relationship(
        "CustomerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    owner_profile: Mapped[Optional["OwnerProfile"]] = relationship(
        "OwnerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    driver_profile: Mapped[Optional["DriverProfile"]] = relationship(
        "DriverProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    cars: Mapped[List["Car"]] = relationship(  # noqa: F821
        "Car",
        back_populates="owner",
    )
    customer_bookings: Mapped[List["Booking"]] = relationship(  # noqa: F821
        "Booking",
        back_populates="customer",
        foreign_keys="[Booking.customer_id]",
    )
    driver_bookings: Mapped[List["Booking"]] = relationship(  # noqa: F821
        "Booking",
        back_populates="driver",
        foreign_keys="[Booking.driver_id]",
    )
    reviews_given: Mapped[List["Review"]] = relationship(  # noqa: F821
        "Review",
        back_populates="customer",
        foreign_keys="[Review.customer_id]",
    )


class Role(Base):
    """Lookup table of platform roles."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        overlaps="user_roles",
    )
    user_roles: Mapped[List["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="roles,users",
    )


class UserRole(Base):
    """Many-to-Many junction mapping users to multiple roles."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_roles", overlaps="roles,users")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles", overlaps="roles,users")


class CustomerProfile(Base):
    """Profile data specific to customers renting vehicles."""

    __tablename__ = "customer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    driving_license_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    license_expiry_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    license_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_license_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
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

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="customer_profile")


class OwnerProfile(Base):
    """Profile data for vehicle owners who list cars on GoCars.

    Sensitive banking information is NOT stored. Non-sensitive mock
    payout references are used.
    """

    __tablename__ = "owner_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    business_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )
    tax_id_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    # Non-sensitive placeholder for owner payout destination
    payout_account_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    payout_status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
    )
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

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="owner_profile")


class DriverProfile(Base):
    """Profile data for drivers providing car-with-driver services."""

    __tablename__ = "driver_profiles"
    __table_args__ = (
        CheckConstraint("experience_years >= 0", name="chk_driver_experience_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    license_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    license_expiry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    experience_years: Mapped[int] = mapped_column(
        SmallInteger,
        default=0,
        nullable=False,
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        default=DriverVerificationStatus.PENDING.value,
        nullable=False,
    )
    duty_status: Mapped[str] = mapped_column(
        String(20),
        default=DriverDutyStatus.OFFLINE.value,
        nullable=False,
    )
    current_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
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

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="driver_profile")
