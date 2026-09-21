"""Tests for Booking Lifecycle State Machine (Phase 6).

Covers:
- Payment confirmation: PENDING_PAYMENT → CONFIRMED
- Trip start: CONFIRMED → IN_PROGRESS (with start odometer)
- Trip completion: IN_PROGRESS → COMPLETED (with end odometer, car.odometer_km synced)
- Odometer validation: end < start rejected with 400
- Cancellation permitted before trip start
- Cancellation rejected once trip is IN_PROGRESS
- Owner can ACCEPT / REJECT a pending booking
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from app.models.enums import (
    RoleName, CarStatus, BookingType, RentalType, BookingStatus,
    DriverVerificationStatus, DriverDutyStatus,
)
from tests.conftest import create_user_helper


def login(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == status.HTTP_200_OK, f"Login failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_available_car(client, owner_headers, admin_headers, odometer=10000):
    suffix = str(uuid.uuid4())[:6].upper()
    payload = {
        "brand": "Tata",
        "model": "Nexon",
        "year": 2023,
        "registration_number": f"DL01LC{suffix}",
        "fuel_type": "ELECTRIC",
        "transmission": "AUTOMATIC",
        "seating_capacity": 5,
        "odometer_km": odometer,
        "rc_number": f"RC-LC-{suffix}",
        "insurance_policy_number": f"INS-LC-{suffix}",
        "insurance_expiry_date": "2028-01-31",
        "city": "Delhi",
        "address": "Connaught Place",
        "hourly_rate": "180.00",
        "daily_rate": "2200.00",
        "weekly_rate": "14000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }
    car_res = client.post("/api/v1/owners/me/cars", json=payload, headers=owner_headers)
    assert car_res.status_code == status.HTTP_201_CREATED, car_res.text
    car_id = car_res.json()["id"]
    client.patch(
        f"/api/v1/admin/cars/{car_id}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=admin_headers,
    )
    return car_id


def create_self_drive_booking(client, customer_headers, car_id, days_offset=3):
    now = datetime.now(timezone.utc)
    return {
        "booking_id": client.post(
            "/api/v1/bookings",
            json={
                "car_id": car_id,
                "booking_type": BookingType.SELF_DRIVE.value,
                "rental_type": RentalType.DAILY.value,
                "start_time": (now + timedelta(days=days_offset)).isoformat(),
                "end_time": (now + timedelta(days=days_offset + 2)).isoformat(),
                "pickup_location": "CP Metro Gate",
                "dropoff_location": "CP Metro Gate",
            },
            headers=customer_headers,
        ).json()["id"]
    }["booking_id"]


# ─────────────────────────────────────────────
# Payment Confirmation
# ─────────────────────────────────────────────

def test_confirm_payment_transitions_to_confirmed(client, db_session):
    """PENDING_PAYMENT booking transitions to CONFIRMED after payment confirmation."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    # Confirm payment
    res = client.post(
        f"/api/v1/bookings/{booking_id}/confirm-payment",
        json={"payment_method": "MOCK_UPI", "transaction_reference": "PAY-TEST-001"},
        headers=head_c,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    assert res.json()["status"] == BookingStatus.CONFIRMED.value


def test_owner_accept_booking(client, db_session):
    """Owner can ACCEPT a PENDING_PAYMENT booking, transitioning it to CONFIRMED."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    assert res.json()["status"] == BookingStatus.CONFIRMED.value


def test_owner_reject_booking(client, db_session):
    """Owner can REJECT a PENDING_PAYMENT booking with a reason."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "REJECT", "rejection_reason": "Vehicle under inspection"},
        headers=head_o,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()
    assert data["status"] == BookingStatus.REJECTED.value
    assert data["cancellation_reason"] == "Vehicle under inspection"


# ─────────────────────────────────────────────
# Trip Start
# ─────────────────────────────────────────────

def test_start_trip_confirmed_to_in_progress(client, db_session):
    """Trip start transitions booking from CONFIRMED to IN_PROGRESS and records odometer."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, odometer=10000)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    # Confirm first (via owner ACCEPT)
    client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )

    # Owner starts trip
    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/start-trip",
        json={"start_odometer": 10050},
        headers=head_o,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()
    assert data["status"] == BookingStatus.IN_PROGRESS.value
    assert data["start_odometer"] == 10050


def test_start_trip_rejects_low_odometer(client, db_session):
    """Trip start with start_odometer < car.odometer_km returns 400."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, odometer=10000)
    booking_id = create_self_drive_booking(client, head_c, car_id)
    client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )

    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/start-trip",
        json={"start_odometer": 9000},  # lower than car's 10000
        headers=head_o,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text


# ─────────────────────────────────────────────
# Trip Completion
# ─────────────────────────────────────────────

def test_complete_trip_in_progress_to_completed(client, db_session):
    """Trip completion transitions IN_PROGRESS → COMPLETED and syncs car.odometer_km."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, odometer=10000)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    # Confirm → Start
    client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )
    client.post(f"/api/v1/owners/me/bookings/{booking_id}/start-trip",
                json={"start_odometer": 10000}, headers=head_o)

    # Complete trip
    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/complete-trip",
        json={"end_odometer": 10350},
        headers=head_o,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()
    assert data["status"] == BookingStatus.COMPLETED.value
    assert data["end_odometer"] == 10350

    # Verify car odometer updated via owner detail endpoint
    car_res = client.get(f"/api/v1/owners/me/cars/{car_id}", headers=head_o)
    assert car_res.status_code == status.HTTP_200_OK
    assert car_res.json()["odometer_km"] == 10350


def test_complete_trip_rejects_end_odometer_below_start(client, db_session):
    """Completing trip with end_odometer < start_odometer returns 400."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, odometer=10000)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )
    client.post(f"/api/v1/owners/me/bookings/{booking_id}/start-trip",
                json={"start_odometer": 10000}, headers=head_o)

    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/complete-trip",
        json={"end_odometer": 9500},  # less than start
        headers=head_o,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text


# ─────────────────────────────────────────────
# Cancellation Rules
# ─────────────────────────────────────────────

def test_customer_cancel_pending_booking(client, db_session):
    """Customer can cancel a PENDING_PAYMENT booking before trip start."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    res = client.post(
        f"/api/v1/customers/me/bookings/{booking_id}/cancel",
        json={"cancellation_reason": "Plans changed"},
        headers=head_c,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    assert res.json()["status"] == BookingStatus.CANCELLED.value


def test_cancellation_rejected_once_in_progress(client, db_session):
    """Customer cannot cancel an IN_PROGRESS trip (400 Bad Request)."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, odometer=10000)
    booking_id = create_self_drive_booking(client, head_c, car_id)

    # Confirm → Start trip
    client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_o,
    )
    client.post(f"/api/v1/owners/me/bookings/{booking_id}/start-trip",
                json={"start_odometer": 10000}, headers=head_o)

    # Attempt cancellation while IN_PROGRESS → 400
    res = client.post(
        f"/api/v1/customers/me/bookings/{booking_id}/cancel",
        json={"cancellation_reason": "Regret"},
        headers=head_c,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST, res.text
