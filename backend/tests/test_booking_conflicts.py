"""Tests for Booking Conflict Prevention (Phase 6).

Covers:
- Double-booking prevention (same vehicle, overlapping interval → 409)
- Blackout period overlap → 409
- Booking permitted once conflicting booking is CANCELLED or REJECTED
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from app.models.enums import RoleName, CarStatus, BookingType, RentalType, BookingStatus
from tests.conftest import create_user_helper


def create_available_car(client, owner_headers, admin_headers):
    suffix = str(uuid.uuid4())[:6].upper()
    payload = {
        "brand": "Toyota",
        "model": "Camry",
        "year": 2022,
        "registration_number": f"MH01CF{suffix}",
        "fuel_type": "PETROL",
        "transmission": "AUTOMATIC",
        "seating_capacity": 5,
        "odometer_km": 5000,
        "rc_number": f"RC-CF-{suffix}",
        "insurance_policy_number": f"INS-CF-{suffix}",
        "insurance_expiry_date": "2027-12-31",
        "city": "Mumbai",
        "address": "BKC, Mumbai",
        "hourly_rate": "150.00",
        "daily_rate": "1800.00",
        "weekly_rate": "11000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }
    car_res = client.post("/api/v1/owners/me/cars", json=payload, headers=owner_headers)
    assert car_res.status_code == status.HTTP_201_CREATED, car_res.text
    car_id = car_res.json()["id"]
    approve_res = client.patch(
        f"/api/v1/admin/cars/{car_id}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=admin_headers,
    )
    assert approve_res.status_code == status.HTTP_200_OK, approve_res.text
    return car_id


def login(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_booking_payload(car_id, start_time, end_time):
    return {
        "car_id": car_id,
        "booking_type": BookingType.SELF_DRIVE.value,
        "rental_type": RentalType.DAILY.value,
        "start_time": start_time,
        "end_time": end_time,
        "pickup_location": "BKC Gate 1",
        "dropoff_location": "BKC Gate 1",
    }


def test_double_booking_same_interval_rejected(client, db_session):
    """Two customers attempting the exact same interval on the same car: second gets 409."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust1, pass_c1 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust2, pass_c2 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c1 = login(client, cust1.email, pass_c1)
    head_c2 = login(client, cust2.email, pass_c2)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)

    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(days=3)).isoformat()
    end_time = (now + timedelta(days=5)).isoformat()

    payload = make_booking_payload(car_id, start_time, end_time)

    # Customer 1 books successfully
    res1 = client.post("/api/v1/bookings", json=payload, headers=head_c1)
    assert res1.status_code == status.HTTP_201_CREATED, res1.text

    # Customer 2 attempts exact same interval → 409
    res2 = client.post("/api/v1/bookings", json=payload, headers=head_c2)
    assert res2.status_code == status.HTTP_409_CONFLICT, res2.text


def test_double_booking_overlapping_interval_rejected(client, db_session):
    """Partially overlapping booking on same car also returns 409."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust1, pass_c1 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust2, pass_c2 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c1 = login(client, cust1.email, pass_c1)
    head_c2 = login(client, cust2.email, pass_c2)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)

    now = datetime.now(timezone.utc)
    # Customer 1: days 3–7
    start1 = (now + timedelta(days=3)).isoformat()
    end1 = (now + timedelta(days=7)).isoformat()
    # Customer 2: days 5–9 (overlaps in the middle)
    start2 = (now + timedelta(days=5)).isoformat()
    end2 = (now + timedelta(days=9)).isoformat()

    res1 = client.post("/api/v1/bookings", json=make_booking_payload(car_id, start1, end1), headers=head_c1)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/api/v1/bookings", json=make_booking_payload(car_id, start2, end2), headers=head_c2)
    assert res2.status_code == status.HTTP_409_CONFLICT


def test_blackout_period_overlap_rejected(client, db_session):
    """Booking that overlaps an active blackout period returns 409."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)

    now = datetime.now(timezone.utc)
    blackout_start = (now + timedelta(days=4)).isoformat()
    blackout_end = (now + timedelta(days=6)).isoformat()

    # Owner creates a blackout period
    bp_res = client.post(
        f"/api/v1/owners/me/cars/{car_id}/blackout-periods",
        json={
            "start_time": blackout_start,
            "end_time": blackout_end,
            "reason": "MAINTENANCE",
        },
        headers=head_o,
    )
    assert bp_res.status_code == status.HTTP_201_CREATED, bp_res.text

    # Customer attempts to book overlapping the blackout window → 409
    book_start = (now + timedelta(days=3)).isoformat()
    book_end = (now + timedelta(days=5)).isoformat()
    res = client.post(
        "/api/v1/bookings",
        json=make_booking_payload(car_id, book_start, book_end),
        headers=head_c,
    )
    assert res.status_code == status.HTTP_409_CONFLICT, res.text


def test_booking_allowed_after_cancel(client, db_session):
    """Once the first booking is CANCELLED, the same interval can be booked again."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust1, pass_c1 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust2, pass_c2 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c1 = login(client, cust1.email, pass_c1)
    head_c2 = login(client, cust2.email, pass_c2)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)

    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(days=3)).isoformat()
    end_time = (now + timedelta(days=5)).isoformat()
    payload = make_booking_payload(car_id, start_time, end_time)

    # Customer 1 books
    res1 = client.post("/api/v1/bookings", json=payload, headers=head_c1)
    assert res1.status_code == status.HTTP_201_CREATED
    booking1_id = res1.json()["id"]

    # Customer 2 blocked
    res2 = client.post("/api/v1/bookings", json=payload, headers=head_c2)
    assert res2.status_code == status.HTTP_409_CONFLICT

    # Customer 1 cancels
    cancel_res = client.post(
        f"/api/v1/customers/me/bookings/{booking1_id}/cancel",
        json={"cancellation_reason": "Change of plans"},
        headers=head_c1,
    )
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == BookingStatus.CANCELLED.value

    # Now Customer 2 can book the same interval
    res3 = client.post("/api/v1/bookings", json=payload, headers=head_c2)
    assert res3.status_code == status.HTTP_201_CREATED, res3.text


def test_booking_allowed_after_rejection(client, db_session):
    """Once owner REJECTS the first booking, the same interval becomes bookable again."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust1, pass_c1 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust2, pass_c2 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c1 = login(client, cust1.email, pass_c1)
    head_c2 = login(client, cust2.email, pass_c2)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)

    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(days=3)).isoformat()
    end_time = (now + timedelta(days=5)).isoformat()
    payload = make_booking_payload(car_id, start_time, end_time)

    # Customer 1 books, Customer 2 blocked
    res1 = client.post("/api/v1/bookings", json=payload, headers=head_c1)
    assert res1.status_code == status.HTTP_201_CREATED
    booking1_id = res1.json()["id"]

    res2 = client.post("/api/v1/bookings", json=payload, headers=head_c2)
    assert res2.status_code == status.HTTP_409_CONFLICT

    # Owner rejects booking 1
    reject_res = client.post(
        f"/api/v1/owners/me/bookings/{booking1_id}/decision",
        json={"decision": "REJECT", "rejection_reason": "Vehicle unavailable"},
        headers=head_o,
    )
    assert reject_res.status_code == status.HTTP_200_OK
    assert reject_res.json()["status"] == BookingStatus.REJECTED.value

    # Customer 2 can now book
    res3 = client.post("/api/v1/bookings", json=payload, headers=head_c2)
    assert res3.status_code == status.HTTP_201_CREATED, res3.text
