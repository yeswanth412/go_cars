"""Public Car Discovery & Search Routes.

Public endpoints for browsing and filtering available vehicles:
- GET /cars: Search available vehicles with multi-field filtering
- GET /cars/{car_id}: Public vehicle details
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.car import (
    CarPublicResponse,
    PaginatedCarPublicResponse,
)
from app.services.car_service import CarService

router = APIRouter(prefix="/cars", tags=["Public Cars"])


@router.get(
    "",
    response_model=PaginatedCarPublicResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Available Cars (Public)",
    description="Search and filter publicly available vehicles. Unapproved, maintenance, suspended, or inactive cars are strictly excluded.",
)
def search_cars(
    city: Optional[str] = Query(None, description="Filter by operating city (case-insensitive substring)"),
    fuel_type: Optional[str] = Query(None, description="Filter by fuel type (PETROL, DIESEL, ELECTRIC, HYBRID, CNG)"),
    transmission: Optional[str] = Query(None, description="Filter by transmission (MANUAL, AUTOMATIC)"),
    min_seats: Optional[int] = Query(None, ge=1, description="Minimum seating capacity"),
    is_self_drive_allowed: Optional[bool] = Query(None, description="Filter by self-drive availability"),
    is_driver_allowed: Optional[bool] = Query(None, description="Filter by car-with-driver availability"),
    min_daily_rate: Optional[Decimal] = Query(None, ge=0, description="Minimum daily rate in INR"),
    max_daily_rate: Optional[Decimal] = Query(None, ge=0, description="Maximum daily rate in INR"),
    brand: Optional[str] = Query(None, description="Filter by manufacturer brand"),
    model: Optional[str] = Query(None, description="Filter by vehicle model"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=50, description="Number of results per page (max 50)"),
    db: Session = Depends(get_db),
) -> PaginatedCarPublicResponse:
    """Public search for available rental vehicles."""
    car_service = CarService(db)
    return car_service.search_public_cars(
        city=city,
        fuel_type=fuel_type,
        transmission=transmission,
        min_seats=min_seats,
        is_self_drive_allowed=is_self_drive_allowed,
        is_driver_allowed=is_driver_allowed,
        min_daily_rate=min_daily_rate,
        max_daily_rate=max_daily_rate,
        brand=brand,
        model=model,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{car_id}",
    response_model=CarPublicResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Public Car Details",
    description="Retrieve public details for an available vehicle. Returns 404 if vehicle is not currently AVAILABLE.",
)
def get_public_car(
    car_id: UUID,
    db: Session = Depends(get_db),
) -> CarPublicResponse:
    """View public vehicle profile."""
    car_service = CarService(db)
    return car_service.get_public_car(car_id)
