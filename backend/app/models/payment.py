"""Payment Transaction SQLAlchemy Model.

Defines:
- Payment (supports mock payments, retries, multiple transactions per booking, and gateway audit logs)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    PaymentMethod,
    PaymentGateway,
    PaymentStatus,
)


class Payment(Base):
    """Payment transaction associated with a booking.

    Note: A booking can have multiple payment attempts/records (1:N),
    supporting retries, partial transactions, and refunds.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="chk_payment_amount_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # 1:N relationship with bookings — NO unique constraint on booking_id
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    transaction_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    payment_method: Mapped[str] = mapped_column(
        String(30),
        default=PaymentMethod.MOCK_UPI.value,
        nullable=False,
    )
    payment_gateway: Mapped[str] = mapped_column(
        String(30),
        default=PaymentGateway.MOCK.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(25),
        default=PaymentStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    gateway_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

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

    # Relationship
    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")  # noqa: F821
