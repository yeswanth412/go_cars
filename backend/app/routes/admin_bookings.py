"""Platform Administration Booking Routes.

Endpoints for platform administrators:
- Listing and filtering all reservations across the platform
- Inspecting comprehensive booking records
- Assigning commercial drivers
- Overriding trip starts and completions
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
    BookingDriverAssignRequest,
    BookingStartTripRequest,
    BookingEndTripRequest,
    BookingResponse,
    PaginatedBookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/admin/bookings", tags=["Admin Bookings"])


@router.get(
    "",
    response_model=PaginatedBookingResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Platform Bookings (Admin)",
    description="Retrieve all reservations across the platform with filtering and pagination. Requires ADMIN role.",
)
def admin_list_bookings(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by booking status"),
    car_id: Optional[UUID] = Query(None, description="Filter by vehicle ID"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    driver_id: Optional[UUID] = Query(None, description="Filter by assigned driver ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> PaginatedBookingResponse:
    """Admin list platform bookings."""
    service = BookingService(db)
    return service.admin_list_bookings(
        status=status_filter,
        car_id=car_id,
        customer_id=customer_id,
        driver_id=driver_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect Booking Details (Admin)",
    description="Retrieve complete transaction specifications, pricing snapshot, customer, vehicle, and driver details. Requires ADMIN role.",
)
def admin_get_booking(
    booking_id: UUID,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Admin fetch single booking."""
    service = BookingService(db)
    return service.admin_get_booking(booking_id=booking_id)


@router.post(
    "/{booking_id}/assign-driver",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Driver to Booking (Admin)",
    description="Assign an approved, online commercial driver to any WITH_DRIVER booking. Requires ADMIN role.",
)
def admin_assign_driver(
    booking_id: UUID,
    request: BookingDriverAssignRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Admin assign driver to booking."""
    service = BookingService(db)
    return service.assign_driver(booking_id=booking_id, driver_id=request.driver_id, assigner=current_admin)


@router.post(
    "/{booking_id}/start-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Override Trip Start (Admin)",
    description="Administrative override to record pickup odometer and transition booking to IN_PROGRESS. Requires ADMIN role.",
)
def admin_start_trip(
    booking_id: UUID,
    request: BookingStartTripRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Admin start trip."""
    service = BookingService(db)
    return service.start_trip(booking_id=booking_id, actor=current_admin, request=request)


@router.post(
    "/{booking_id}/complete-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Override Trip Completion (Admin)",
    description="Administrative override to record dropoff odometer, synchronize car odometer, and transition booking to COMPLETED. Requires ADMIN role.",
)
def admin_complete_trip(
    booking_id: UUID,
    request: BookingEndTripRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Admin complete trip."""
    service = BookingService(db)
    return service.complete_trip(booking_id=booking_id, actor=current_admin, request=request)
