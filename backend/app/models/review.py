"""Review and Rating SQLAlchemy Model.

Defines:
- Review (customer feedback and 1-5 star ratings for cars and drivers on completed trips)
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Review(Base):
    """Customer ratings and comments for a completed booking trip."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("car_rating BETWEEN 1 AND 5", name="chk_review_car_rating_range"),
        CheckConstraint(
            "driver_rating IS NULL OR (driver_rating BETWEEN 1 AND 5)",
            name="chk_review_driver_rating_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # 1 Review per Booking (UNIQUE constraint)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
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

    # Car Evaluation
    car_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    car_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Driver Evaluation (only present for WITH_DRIVER bookings)
    driver_rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    driver_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="review")  # noqa: F821
    customer: Mapped["User"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[customer_id],
        back_populates="reviews_given",
    )
    car: Mapped["Car"] = relationship("Car", back_populates="reviews")  # noqa: F821
    driver: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User",
        foreign_keys=[driver_id],
    )
