"""Car Fleet Service.

Coordinates business rules, ownership authorization, platform-controlled pricing enforcement,
public discovery filtering, and administrative lifecycle workflows.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.enums import CarStatus
from app.models.car import Car
from app.repositories.car_repository import CarRepository
from app.schemas.car import (
    CarCreateRequest,
    CarUpdateRequest,
    CarApprovalRequest,
    CarStatusUpdateRequest,
    CarDetailResponse,
    CarPublicResponse,
    PaginatedCarPublicResponse,
    PaginatedCarDetailResponse,
)


class CarService:
    """Service managing vehicle fleet lifecycle, authorization, and discovery."""

    def __init__(self, db: Session):
        self.db = db
        self.car_repo = CarRepository(db)

    def _verify_owner(self, car: Car, owner_id: UUID):
        """Ownership authorization check."""
        if car.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access or modify this vehicle",
            )

    def create_car(self, owner_id: UUID, request: CarCreateRequest) -> CarDetailResponse:
        """Owner registers a new vehicle. Status defaults to PENDING_APPROVAL."""
        # Uniqueness check on registration plate number
        cleaned_reg = request.registration_number.strip().upper()
        if self.car_repo.get_by_registration_number(cleaned_reg):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A vehicle with registration number '{cleaned_reg}' is already registered",
            )

        try:
            car = self.car_repo.create(
                owner_id=owner_id,
                brand=request.brand,
                model=request.model,
                year=request.year,
                registration_number=cleaned_reg,
                fuel_type=request.fuel_type.value,
                transmission=request.transmission.value,
                seating_capacity=request.seating_capacity,
                odometer_km=request.odometer_km,
                rc_number=request.rc_number,
                insurance_policy_number=request.insurance_policy_number,
                insurance_expiry_date=request.insurance_expiry_date,
                city=request.city,
                address=request.address,
                hourly_rate=request.hourly_rate,
                daily_rate=request.daily_rate,
                weekly_rate=request.weekly_rate,
                is_self_drive_allowed=request.is_self_drive_allowed,
                is_driver_allowed=request.is_driver_allowed,
                status=CarStatus.PENDING_APPROVAL.value,
            )
            self.db.commit()
            self.db.refresh(car)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.car_repo.get_by_id_with_relations(car.id)
        return CarDetailResponse.model_validate(refreshed or car)

    def get_owner_car(self, car_id: UUID, owner_id: UUID) -> CarDetailResponse:
        """Fetch full details of an owned car."""
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        self._verify_owner(car, owner_id)
        return CarDetailResponse.model_validate(car)

    def list_owner_cars(
        self,
        owner_id: UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCarDetailResponse:
        """List vehicles belonging exclusively to the authenticated owner."""
        cars, total = self.car_repo.list_by_owner(
            owner_id=owner_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        items = [CarDetailResponse.model_validate(c) for c in cars]
        return PaginatedCarDetailResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    def update_owner_car(
        self,
        car_id: UUID,
        owner_id: UUID,
        request: CarUpdateRequest,
    ) -> CarDetailResponse:
        """Owner updates permitted operational attributes.

        Rates, status, registration, and ownership are strictly protected.
        """
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        self._verify_owner(car, owner_id)

        update_data = request.model_dump(exclude_unset=True)
        if not update_data:
            return CarDetailResponse.model_validate(car)

        try:
            self.car_repo.update(car, update_data)
            self.db.commit()
            self.db.refresh(car)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.car_repo.get_by_id_with_relations(car_id)
        return CarDetailResponse.model_validate(refreshed or car)

    def delete_owner_car(self, car_id: UUID, owner_id: UUID) -> dict:
        """Safely delete or archive a vehicle.

        If the vehicle has associated historical bookings, hard deletion is prohibited
        to prevent database integrity violations; the vehicle is archived to INACTIVE instead.
        """
        car = self.car_repo.get_by_id(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        self._verify_owner(car, owner_id)

        booking_count = self.car_repo.count_bookings(car_id)
        try:
            if booking_count > 0:
                # Soft archival
                self.car_repo.update_status(car, CarStatus.INACTIVE.value)
                self.db.commit()
                return {
                    "message": "Vehicle has existing booking history. It has been deactivated and archived as INACTIVE.",
                    "status": CarStatus.INACTIVE.value,
                    "car_id": str(car_id),
                }
            else:
                # Hard delete
                self.car_repo.delete(car)
                self.db.commit()
                return {
                    "message": "Vehicle deleted successfully.",
                    "car_id": str(car_id),
                }
        except Exception:
            self.db.rollback()
            raise

    def search_public_cars(
        self,
        city: Optional[str] = None,
        fuel_type: Optional[str] = None,
        transmission: Optional[str] = None,
        min_seats: Optional[int] = None,
        is_self_drive_allowed: Optional[bool] = None,
        is_driver_allowed: Optional[bool] = None,
        min_daily_rate: Optional[Decimal] = None,
        max_daily_rate: Optional[Decimal] = None,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCarPublicResponse:
        """Public car discovery. Exposes ONLY cars in AVAILABLE state with safe public attributes."""
        cars, total = self.car_repo.search_public(
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
        items = [CarPublicResponse.model_validate(c) for c in cars]
        return PaginatedCarPublicResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    def get_public_car(self, car_id: UUID) -> CarPublicResponse:
        """Public car detail view. Strictly forbidden if car is not in AVAILABLE status."""
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car or car.status != CarStatus.AVAILABLE.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found or is currently not available for rental",
            )
        return CarPublicResponse.model_validate(car)

    def admin_list_cars(
        self,
        status_filter: Optional[str] = None,
        city: Optional[str] = None,
        brand: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCarDetailResponse:
        """Administrative overview of all vehicles across all owners and statuses."""
        cars, total = self.car_repo.list_all_admin(
            status=status_filter,
            city=city,
            brand=brand,
            owner_id=owner_id,
            page=page,
            page_size=page_size,
        )
        items = [CarDetailResponse.model_validate(c) for c in cars]
        return PaginatedCarDetailResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    def admin_get_car(self, car_id: UUID) -> CarDetailResponse:
        """Administrative inspection of a vehicle record."""
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        return CarDetailResponse.model_validate(car)

    def admin_approve_car(self, car_id: UUID, request: CarApprovalRequest) -> CarDetailResponse:
        """Admin approves (AVAILABLE) or rejects (REJECTED) a vehicle."""
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )

        try:
            self.car_repo.update_status(car, request.status.value)
            self.db.commit()
            self.db.refresh(car)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.car_repo.get_by_id_with_relations(car_id)
        return CarDetailResponse.model_validate(refreshed or car)

    def admin_update_status(self, car_id: UUID, request: CarStatusUpdateRequest) -> CarDetailResponse:
        """Admin updates operational status (e.g. to MAINTENANCE, SUSPENDED, or AVAILABLE)."""
        car = self.car_repo.get_by_id_with_relations(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )

        try:
            self.car_repo.update_status(car, request.status.value)
            self.db.commit()
            self.db.refresh(car)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.car_repo.get_by_id_with_relations(car_id)
        return CarDetailResponse.model_validate(refreshed or car)
