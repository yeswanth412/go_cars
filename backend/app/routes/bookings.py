"""Customer Booking Routes.

Endpoints for rental reservations, pricing estimations, mock payment confirmation,
history listings, and pre-trip cancellations.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.booking import (
    BookingCreateRequest,
    BookingPricingEstimateRequest,
    BookingPricingEstimateResponse,
    BookingPaymentConfirmRequest,
    BookingCancelRequest,
    BookingResponse,
    PaginatedBookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(tags=["Bookings"])


@router.post(
    "/bookings/estimate-price",
    response_model=BookingPricingEstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate Rental Pricing",
    description="Calculate upfront deterministic pricing breakdown for a vehicle rental without creating a reservation.",
)
def estimate_pricing(
    request: BookingPricingEstimateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingPricingEstimateResponse:
    """Preview rental pricing."""
    service = BookingService(db)
    return service.estimate_pricing(request)


@router.post(
    "/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Reservation (Customer)",
    description="Reserve a vehicle for self-drive or with-driver. Locks vehicle row (SELECT FOR UPDATE) to eliminate double-booking. Requires CUSTOMER role.",
)
def create_booking(
    request: BookingCreateRequest,
    current_customer: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Create new booking reservation."""
    service = BookingService(db)
    return service.create_booking(customer_id=current_customer.id, request=request)


@router.post(
    "/bookings/{booking_id}/confirm-payment",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Payment (Customer)",
    description="Confirm payment for a pending reservation, transitioning status from PENDING_PAYMENT to CONFIRMED. Requires CUSTOMER role.",
)
def confirm_payment(
    booking_id: UUID,
    request: BookingPaymentConfirmRequest,
    current_customer: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Confirm payment for a booking."""
    service = BookingService(db)
    return service.confirm_payment(booking_id=booking_id, customer_id=current_customer.id, request=request)


@router.get(
    "/customers/me/bookings",
    response_model=PaginatedBookingResponse,
    status_code=status.HTTP_200_OK,
    summary="List My Bookings (Customer)",
    description="Retrieve all reservations booked by the authenticated customer with pagination and status filters. Requires CUSTOMER role.",
)
def list_customer_bookings(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING_PAYMENT, CONFIRMED, COMPLETED)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_customer: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> PaginatedBookingResponse:
    """List customer booking history."""
    service = BookingService(db)
    return service.list_customer_bookings(
        customer_id=current_customer.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/customers/me/bookings/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Booking Details (Customer)",
    description="Retrieve details of a single reservation belonging to the authenticated customer. Requires CUSTOMER role.",
)
def get_customer_booking(
    booking_id: UUID,
    current_customer: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Fetch single booking for customer."""
    service = BookingService(db)
    return service.get_customer_booking(booking_id=booking_id, customer_id=current_customer.id)


@router.post(
    "/customers/me/bookings/{booking_id}/cancel",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Booking (Customer)",
    description="Cancel a reservation strictly before the scheduled start time. Cancellations after trip commencement are forbidden. Requires CUSTOMER role.",
)
def customer_cancel_booking(
    booking_id: UUID,
    request: BookingCancelRequest,
    current_customer: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Cancel booking before trip start."""
    service = BookingService(db)
    return service.customer_cancel_booking(
        booking_id=booking_id,
        customer_id=current_customer.id,
        request=request,
    )
