"""Fleet Owner Booking Management Routes.

Endpoints for fleet owners:
- Viewing reservations for owned vehicles
- Accepting or rejecting pending reservations
- Assigning commercial drivers
- Vehicle handover (trip start) & return (trip completion with odometer synchronization)
- Pre-trip owner cancellations
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.booking import (
    BookingDecisionRequest,
    BookingDriverAssignRequest,
    BookingCancelRequest,
    BookingStartTripRequest,
    BookingEndTripRequest,
    BookingResponse,
    PaginatedBookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/owners/me/bookings", tags=["Owner Bookings"])


@router.get(
    "",
    response_model=PaginatedBookingResponse,
    status_code=status.HTTP_200_OK,
    summary="List Fleet Bookings (Owner)",
    description="Retrieve all reservations booked on vehicles owned by the authenticated owner. Requires OWNER role.",
)
def list_owner_bookings(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING_PAYMENT, CONFIRMED, IN_PROGRESS)"),
    car_id: Optional[UUID] = Query(None, description="Filter by specific vehicle ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> PaginatedBookingResponse:
    """List bookings for owner's fleet."""
    service = BookingService(db)
    return service.list_owner_bookings(
        owner_id=current_owner.id,
        status=status_filter,
        car_id=car_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Fleet Booking Details (Owner)",
    description="Retrieve detailed specifications and customer info for a booking on an owned vehicle. Requires OWNER role.",
)
def get_owner_booking(
    booking_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Fetch single booking on owned car."""
    service = BookingService(db)
    return service.get_owner_booking(booking_id=booking_id, owner_id=current_owner.id)


@router.post(
    "/{booking_id}/decision",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept or Reject Reservation (Owner)",
    description="Accept (CONFIRMED) or reject (REJECTED + reason) a pending reservation for an owned vehicle. Requires OWNER role.",
)
def owner_decide_booking(
    booking_id: UUID,
    request: BookingDecisionRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Accept or reject booking."""
    service = BookingService(db)
    return service.owner_decide_booking(booking_id=booking_id, owner_id=current_owner.id, request=request)


@router.post(
    "/{booking_id}/assign-driver",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Driver to Booking (Owner)",
    description="Assign an approved, online commercial driver to a WITH_DRIVER booking on an owned vehicle. Checks for overlapping assignments. Requires OWNER role.",
)
def owner_assign_driver(
    booking_id: UUID,
    request: BookingDriverAssignRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Assign driver to owned car booking."""
    service = BookingService(db)
    return service.assign_driver(booking_id=booking_id, driver_id=request.driver_id, assigner=current_owner)


@router.post(
    "/{booking_id}/start-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Trip / Handover Vehicle (Owner)",
    description="Record pickup odometer and transition booking to IN_PROGRESS. Requires OWNER role.",
)
def owner_start_trip(
    booking_id: UUID,
    request: BookingStartTripRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Start trip and record start odometer."""
    service = BookingService(db)
    return service.start_trip(booking_id=booking_id, actor=current_owner, request=request)


@router.post(
    "/{booking_id}/complete-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete Trip / Vehicle Returned (Owner)",
    description="Record dropoff odometer, synchronize vehicle cumulative odometer, and transition booking to COMPLETED. Requires OWNER role.",
)
def owner_complete_trip(
    booking_id: UUID,
    request: BookingEndTripRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Complete trip and update car odometer."""
    service = BookingService(db)
    return service.complete_trip(booking_id=booking_id, actor=current_owner, request=request)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Fleet Booking (Owner)",
    description="Cancel a reservation on an owned car strictly before the scheduled start time. Requires OWNER role.",
)
def owner_cancel_booking(
    booking_id: UUID,
    request: BookingCancelRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Cancel booking before start."""
    service = BookingService(db)
    return service.owner_cancel_booking(booking_id=booking_id, owner_id=current_owner.id, request=request)
