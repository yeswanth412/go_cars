"""Booking Service.

Implements business logic for:
- Deterministic platform pricing calculation and price snapshotting
- Transaction-safe reservation creation with SELECT ... FOR UPDATE row locking
- Multi-factor availability checking (car status, blackout periods, active bookings)
- Mock payment execution & confirmation
- Commercial driver assignment with eligibility, duty status, and conflict checks
- Vehicle handover & trip execution (start/end trip with odometer synchronization)
- Safe pre-trip cancellations and refunds
- Role-scoped history queries for Customers, Fleet Owners, Drivers, and Admins
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Optional, Tuple
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.booking import Booking
from app.models.car import Car, CarBlackoutPeriod
from app.models.enums import (
    BookingType,
    RentalType,
    BookingStatus,
    CarStatus,
    DriverVerificationStatus,
    DriverDutyStatus,
    RoleName,
)
from app.models.user import User, DriverProfile
from app.repositories.booking_repository import BookingRepository
from app.repositories.car_repository import CarRepository
from app.repositories.blackout_period_repository import BlackoutPeriodRepository
from app.schemas.booking import (
    BookingCreateRequest,
    BookingPricingEstimateRequest,
    BookingPricingEstimateResponse,
    BookingPaymentConfirmRequest,
    BookingDecisionRequest,
    BookingDriverAssignRequest,
    BookingCancelRequest,
    BookingStartTripRequest,
    BookingEndTripRequest,
    BookingResponse,
    PaginatedBookingResponse,
)


class BookingService:
    """Service governing car rental bookings and reservation lifecycles."""

    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.car_repo = CarRepository(db)
        self.blackout_repo = BlackoutPeriodRepository(db)

    # =========================================================================
    # Pricing Engine
    # =========================================================================

    def calculate_pricing(
        self,
        car: Car,
        booking_type: BookingType,
        rental_type: RentalType,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Calculate deterministic platform pricing breakdown.

        Platform rules:
        - HOURLY: unit_rate = car.hourly_rate; driver = ₹75/hr
        - DAILY: unit_rate = car.daily_rate; driver = ₹500/day
        - WEEKLY: unit_rate = car.weekly_rate; driver = ₹3000/week
        - Platform Fee: 5% of (base + driver)
        - GST Tax: 18% of (base + driver + platform fee)
        - Security Deposit: ₹2,000 refundable
        """
        duration_seconds = (end_time - start_time).total_seconds()
        duration_hours = Decimal(str(round(duration_seconds / 3600, 2)))

        if rental_type == RentalType.HOURLY:
            units = max(1, math.ceil(duration_seconds / 3600))
            unit_rate = car.hourly_rate
            base_amount = Decimal(units) * unit_rate
            driver_rate_per_unit = Decimal("75.00")
        elif rental_type == RentalType.DAILY:
            units = max(1, math.ceil(duration_seconds / 86400))
            unit_rate = car.daily_rate
            base_amount = Decimal(units) * unit_rate
            driver_rate_per_unit = Decimal("500.00")
        elif rental_type == RentalType.WEEKLY:
            units = max(1, math.ceil(duration_seconds / (7 * 86400)))
            unit_rate = car.weekly_rate
            base_amount = Decimal(units) * unit_rate
            driver_rate_per_unit = Decimal("3000.00")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported rental tier: {rental_type}",
            )

        driver_charge = (
            (Decimal(units) * driver_rate_per_unit)
            if booking_type == BookingType.WITH_DRIVER
            else Decimal("0.00")
        )

        subtotal = base_amount + driver_charge
        platform_fee = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        taxable_amount = subtotal + platform_fee
        tax_amount = (taxable_amount * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        security_deposit = Decimal("2000.00")
        discount_amount = Decimal("0.00")
        total_amount = subtotal + platform_fee + tax_amount + security_deposit - discount_amount

        return {
            "car_id": car.id,
            "booking_type": booking_type,
            "rental_type": rental_type,
            "duration_hours": duration_hours,
            "billable_units": units,
            "unit_rate": unit_rate,
            "base_amount": base_amount.quantize(Decimal("0.01")),
            "driver_charge": driver_charge.quantize(Decimal("0.01")),
            "platform_fee": platform_fee,
            "tax_amount": tax_amount,
            "security_deposit": security_deposit,
            "discount_amount": discount_amount,
            "total_amount": total_amount.quantize(Decimal("0.01")),
            "currency": "INR",
        }

    def estimate_pricing(self, request: BookingPricingEstimateRequest) -> BookingPricingEstimateResponse:
        """Preview rental charges without persisting a booking."""
        car = self.car_repo.get_by_id(request.car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        pricing = self.calculate_pricing(
            car=car,
            booking_type=request.booking_type,
            rental_type=request.rental_type,
            start_time=request.start_time,
            end_time=request.end_time,
        )
        return BookingPricingEstimateResponse.model_validate(pricing)

    # =========================================================================
    # Booking Creation (SELECT ... FOR UPDATE)
    # =========================================================================

    def create_booking(self, customer_id: UUID, request: BookingCreateRequest) -> BookingResponse:
        """Create a reservation with row-level locking and comprehensive availability validation."""
        start_time = request.start_time
        end_time = request.end_time

        try:
            # 1. Row-level lock on the vehicle inside the transaction
            stmt = select(Car).where(Car.id == request.car_id).with_for_update()
            car = self.db.scalars(stmt).first()

            if not car:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Car not found",
                )

            # 2. Status check
            if car.status != CarStatus.AVAILABLE.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Car is not available for reservation (current status: {car.status})",
                )

            # 3. Rental mode permission check
            if request.booking_type == BookingType.SELF_DRIVE and not car.is_self_drive_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This vehicle does not support self-drive rentals",
                )
            if request.booking_type == BookingType.WITH_DRIVER and not car.is_driver_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This vehicle does not support chauffeur / with-driver rentals",
                )

            # 4. Anti-self-booking rule
            if car.owner_id == customer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vehicle owners cannot book their own vehicles",
                )

            # 5. Check blackout period overlap while holding lock
            blackout_stmt = select(CarBlackoutPeriod).where(
                CarBlackoutPeriod.car_id == request.car_id,
                CarBlackoutPeriod.start_time < end_time,
                CarBlackoutPeriod.end_time > start_time,
            )
            blackout_conflict = self.db.scalars(blackout_stmt).first()
            if blackout_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Vehicle is unavailable due to scheduled maintenance or blackout period during this interval",
                )

            # 6. Check active booking overlap while holding lock
            has_booking_overlap = self.booking_repo.check_car_overlap(
                car_id=request.car_id,
                start_time=start_time,
                end_time=end_time,
            )
            if has_booking_overlap:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Vehicle already has a confirmed or active reservation during this interval",
                )

            # 7. Compute deterministic platform pricing snapshot
            pricing = self.calculate_pricing(
                car=car,
                booking_type=request.booking_type,
                rental_type=request.rental_type,
                start_time=start_time,
                end_time=end_time,
            )

            # 8. Persist booking
            booking = self.booking_repo.create(
                customer_id=customer_id,
                car_id=request.car_id,
                booking_type=request.booking_type.value,
                rental_type=request.rental_type.value,
                start_time=start_time,
                end_time=end_time,
                pickup_location=request.pickup_location,
                dropoff_location=request.dropoff_location,
                base_amount=pricing["base_amount"],
                driver_charge=pricing["driver_charge"],
                platform_fee=pricing["platform_fee"],
                tax_amount=pricing["tax_amount"],
                security_deposit=pricing["security_deposit"],
                total_amount=pricing["total_amount"],
                status=BookingStatus.PENDING_PAYMENT.value,
            )
            self.db.commit()
            self.db.refresh(booking)

        except HTTPException:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # Payment Confirmation
    # =========================================================================

    def confirm_payment(
        self,
        booking_id: UUID,
        customer_id: UUID,
        request: BookingPaymentConfirmRequest,
    ) -> BookingResponse:
        """Confirm payment and transition booking from PENDING_PAYMENT to CONFIRMED."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found",
            )
        if booking.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized access to this booking",
            )
        if booking.status != BookingStatus.PENDING_PAYMENT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm payment for booking with status: {booking.status}",
            )

        try:
            self.booking_repo.update_status(booking, BookingStatus.CONFIRMED.value)
            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # Owner Decision (Accept / Reject)
    # =========================================================================

    def owner_decide_booking(
        self,
        booking_id: UUID,
        owner_id: UUID,
        request: BookingDecisionRequest,
    ) -> BookingResponse:
        """Fleet owner accepts or rejects a pending booking reservation."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found",
            )
        if booking.car.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You do not own the vehicle for this booking",
            )
        if booking.status != BookingStatus.PENDING_PAYMENT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Decision can only be made on PENDING_PAYMENT bookings (current: {booking.status})",
            )

        try:
            if request.decision == "ACCEPT":
                self.booking_repo.update_status(booking, BookingStatus.CONFIRMED.value)
            elif request.decision == "REJECT":
                self.booking_repo.update_status(booking, BookingStatus.REJECTED.value)
                booking.cancellation_reason = request.rejection_reason
                self.db.flush()
            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # Driver Assignment
    # =========================================================================

    def assign_driver(
        self,
        booking_id: UUID,
        driver_id: UUID,
        assigner: User,
    ) -> BookingResponse:
        """Assign a verified, online commercial driver to a WITH_DRIVER booking."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found",
            )

        # Authorization: Must be Admin or Vehicle Owner
        is_admin = any(r.name == RoleName.ADMIN.value for r in assigner.roles)
        is_owner = booking.car.owner_id == assigner.id
        if not (is_admin or is_owner):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only platform administrators or the vehicle owner can assign drivers",
            )

        if booking.booking_type != BookingType.WITH_DRIVER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver assignment is only applicable for WITH_DRIVER bookings",
            )
        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot assign driver to booking in {booking.status} status",
            )

        # Fetch candidate driver
        driver_user = self.db.scalars(select(User).where(User.id == driver_id)).first()
        if not driver_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver user account not found",
            )
        has_driver_role = any(r.name == RoleName.DRIVER.value for r in driver_user.roles)
        if not has_driver_role or not driver_user.driver_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified user does not have an active DRIVER profile",
            )

        driver_profile: DriverProfile = driver_user.driver_profile
        if driver_profile.verification_status != DriverVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver is not approved (verification status: {driver_profile.verification_status})",
            )
        if driver_profile.duty_status != DriverDutyStatus.ONLINE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Driver is not currently available (duty status: {driver_profile.duty_status})",
            )

        # Check driver overlap
        has_overlap = self.booking_repo.check_driver_overlap(
            driver_id=driver_id,
            start_time=booking.start_time,
            end_time=booking.end_time,
            exclude_booking_id=booking.id,
        )
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected driver already has a conflicting trip assignment during this interval",
            )

        try:
            self.booking_repo.assign_driver(booking, driver_id)
            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # Trip Execution (Start & Complete Trip)
    # =========================================================================

    def start_trip(
        self,
        booking_id: UUID,
        actor: User,
        request: BookingStartTripRequest,
    ) -> BookingResponse:
        """Handover vehicle and start trip, recording pickup odometer."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        is_admin = any(r.name == RoleName.ADMIN.value for r in actor.roles)
        is_owner = booking.car.owner_id == actor.id
        is_assigned_driver = booking.driver_id == actor.id
        if not (is_admin or is_owner or is_assigned_driver):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only the vehicle owner, assigned driver, or admin can start the trip",
            )

        if booking.status != BookingStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trip can only be started from CONFIRMED status (current: {booking.status})",
            )

        if request.start_odometer < booking.car.odometer_km:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Start odometer ({request.start_odometer} km) cannot be lower than vehicle's current odometer ({booking.car.odometer_km} km)",
            )

        try:
            now_utc = datetime.now(timezone.utc)
            self.booking_repo.record_trip_start(booking, request.start_odometer, now_utc)

            # Update driver duty status if applicable
            if booking.driver and booking.driver.driver_profile:
                booking.driver.driver_profile.duty_status = DriverDutyStatus.ON_TRIP.value

            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    def complete_trip(
        self,
        booking_id: UUID,
        actor: User,
        request: BookingEndTripRequest,
    ) -> BookingResponse:
        """Complete trip, record dropoff odometer, and update vehicle's cumulative mileage."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        is_admin = any(r.name == RoleName.ADMIN.value for r in actor.roles)
        is_owner = booking.car.owner_id == actor.id
        is_assigned_driver = booking.driver_id == actor.id
        if not (is_admin or is_owner or is_assigned_driver):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Only the vehicle owner, assigned driver, or admin can complete the trip",
            )

        if booking.status != BookingStatus.IN_PROGRESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only IN_PROGRESS trips can be completed (current: {booking.status})",
            )

        start_odo = booking.start_odometer or booking.car.odometer_km
        if request.end_odometer < start_odo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"End odometer ({request.end_odometer} km) cannot be lower than trip start odometer ({start_odo} km)",
            )

        try:
            now_utc = datetime.now(timezone.utc)
            self.booking_repo.record_trip_end(booking, request.end_odometer, now_utc)

            # Synchronize car cumulative odometer reading
            booking.car.odometer_km = request.end_odometer

            # Return driver duty status to ONLINE
            if booking.driver and booking.driver.driver_profile:
                booking.driver.driver_profile.duty_status = DriverDutyStatus.ONLINE.value

            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # Cancellation Management
    # =========================================================================

    def customer_cancel_booking(
        self,
        booking_id: UUID,
        customer_id: UUID,
        request: BookingCancelRequest,
    ) -> BookingResponse:
        """Customer cancels their reservation before trip start."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.customer_id != customer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to this booking")

        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel booking with status: {booking.status}. Once trip is IN_PROGRESS, cancellation is forbidden.",
            )

        now_utc = datetime.now(timezone.utc)
        if booking.start_time <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cancellation is only permitted strictly before the scheduled start time",
            )

        try:
            self.booking_repo.record_cancellation(
                booking=booking,
                cancelled_by_id=customer_id,
                reason=request.cancellation_reason,
                fee=Decimal("0.00"),
                refund=booking.total_amount,
            )
            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    def owner_cancel_booking(
        self,
        booking_id: UUID,
        owner_id: UUID,
        request: BookingCancelRequest,
    ) -> BookingResponse:
        """Owner cancels reservation on their vehicle before trip start."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.car.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: You do not own this vehicle")

        if booking.status not in (BookingStatus.PENDING_PAYMENT.value, BookingStatus.CONFIRMED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel booking with status: {booking.status}",
            )

        now_utc = datetime.now(timezone.utc)
        if booking.start_time <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cancellation is only permitted strictly before the scheduled start time",
            )

        try:
            self.booking_repo.record_cancellation(
                booking=booking,
                cancelled_by_id=owner_id,
                reason=request.cancellation_reason,
                fee=Decimal("0.00"),
                refund=booking.total_amount,
            )
            self.db.commit()
            self.db.refresh(booking)
        except Exception:
            self.db.rollback()
            raise

        refreshed = self.booking_repo.get_by_id_with_relations(booking.id)
        return BookingResponse.model_validate(refreshed or booking)

    # =========================================================================
    # History & Queries
    # =========================================================================

    def list_customer_bookings(
        self,
        customer_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedBookingResponse:
        """List customer's reservations with pagination."""
        items, total = self.booking_repo.list_by_customer(customer_id, status, page, page_size)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return PaginatedBookingResponse(
            items=[BookingResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_customer_booking(self, booking_id: UUID, customer_id: UUID) -> BookingResponse:
        """Fetch single reservation for a customer."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.customer_id != customer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to this booking")
        return BookingResponse.model_validate(booking)

    def list_owner_bookings(
        self,
        owner_id: UUID,
        status: Optional[str] = None,
        car_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedBookingResponse:
        """List reservations across an owner's fleet."""
        items, total = self.booking_repo.list_by_owner(owner_id, status, car_id, page, page_size)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return PaginatedBookingResponse(
            items=[BookingResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_owner_booking(self, booking_id: UUID, owner_id: UUID) -> BookingResponse:
        """Fetch single reservation for an owner's vehicle."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.car.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: You do not own this vehicle")
        return BookingResponse.model_validate(booking)

    def list_driver_trips(
        self,
        driver_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedBookingResponse:
        """List assigned trips for a commercial driver."""
        items, total = self.booking_repo.list_by_driver(driver_id, status, page, page_size)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return PaginatedBookingResponse(
            items=[BookingResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def admin_list_bookings(
        self,
        status: Optional[str] = None,
        car_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        driver_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedBookingResponse:
        """Admin list all platform reservations with filters."""
        items, total = self.booking_repo.list_all_admin(status, car_id, customer_id, driver_id, page, page_size)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return PaginatedBookingResponse(
            items=[BookingResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def admin_get_booking(self, booking_id: UUID) -> BookingResponse:
        """Admin inspect any reservation."""
        booking = self.booking_repo.get_by_id_with_relations(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        return BookingResponse.model_validate(booking)
