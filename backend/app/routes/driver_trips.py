"""Commercial Driver Trip Routes.

Endpoints for drivers to view assigned trips, start trips, and complete trips.
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
    BookingStartTripRequest,
    BookingEndTripRequest,
    BookingResponse,
    PaginatedBookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/drivers/me/trips", tags=["Driver Trips"])


@router.get(
    "",
    response_model=PaginatedBookingResponse,
    status_code=status.HTTP_200_OK,
    summary="List Assigned Trips (Driver)",
    description="Retrieve all trips assigned to the authenticated commercial driver. Requires DRIVER role.",
)
def list_driver_trips(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. CONFIRMED, IN_PROGRESS, COMPLETED)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_driver: User = Depends(require_roles(RoleName.DRIVER.value)),
    db: Session = Depends(get_db),
) -> PaginatedBookingResponse:
    """List assigned trips for the driver."""
    service = BookingService(db)
    return service.list_driver_trips(
        driver_id=current_driver.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{booking_id}/start-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Trip (Driver)",
    description="Record pickup odometer and transition booking to IN_PROGRESS. Updates driver duty status to ON_TRIP. Requires DRIVER role.",
)
def driver_start_trip(
    booking_id: UUID,
    request: BookingStartTripRequest,
    current_driver: User = Depends(require_roles(RoleName.DRIVER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Driver starts assigned trip."""
    service = BookingService(db)
    return service.start_trip(booking_id=booking_id, actor=current_driver, request=request)


@router.post(
    "/{booking_id}/complete-trip",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete Trip (Driver)",
    description="Record dropoff odometer and transition booking to COMPLETED. Updates driver duty status to ONLINE and synchronizes car odometer. Requires DRIVER role.",
)
def driver_complete_trip(
    booking_id: UUID,
    request: BookingEndTripRequest,
    current_driver: User = Depends(require_roles(RoleName.DRIVER.value)),
    db: Session = Depends(get_db),
) -> BookingResponse:
    """Driver completes assigned trip."""
    service = BookingService(db)
    return service.complete_trip(booking_id=booking_id, actor=current_driver, request=request)
