"""Tests for Booking Authorization & Role Isolation (Phase 6).

Covers:
- Cross-customer isolation: Customer A cannot access Customer B's booking
- Cross-owner isolation: Owner A cannot manage Owner B's fleet bookings
- Admin can inspect and manage all platform reservations
- Unauthenticated requests rejected (401)
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from app.models.enums import RoleName, CarStatus, BookingType, RentalType
from tests.conftest import create_user_helper


def login(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == status.HTTP_200_OK, f"Login failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_available_car(client, owner_headers, admin_headers):
    suffix = str(uuid.uuid4())[:6].upper()
    payload = {
        "brand": "Ford",
        "model": "EcoSport",
        "year": 2021,
        "registration_number": f"TN01AZ{suffix}",
        "fuel_type": "DIESEL",
        "transmission": "MANUAL",
        "seating_capacity": 5,
        "odometer_km": 20000,
        "rc_number": f"RC-AZ-{suffix}",
        "insurance_policy_number": f"INS-AZ-{suffix}",
        "insurance_expiry_date": "2027-09-30",
        "city": "Chennai",
        "address": "Anna Nagar",
        "hourly_rate": "120.00",
        "daily_rate": "1500.00",
        "weekly_rate": "9000.00",
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


def make_booking(client, customer_headers, car_id, days_offset=3):
    now = datetime.now(timezone.utc)
    res = client.post(
        "/api/v1/bookings",
        json={
            "car_id": car_id,
            "booking_type": BookingType.SELF_DRIVE.value,
            "rental_type": RentalType.DAILY.value,
            "start_time": (now + timedelta(days=days_offset)).isoformat(),
            "end_time": (now + timedelta(days=days_offset + 2)).isoformat(),
            "pickup_location": "Anna Nagar West",
            "dropoff_location": "Anna Nagar West",
        },
        headers=customer_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED, res.text
    return res.json()["id"]


# ─────────────────────────────────────────────
# Cross-Customer Isolation
# ─────────────────────────────────────────────

def test_customer_cannot_view_another_customers_booking(client, db_session):
    """Customer B cannot fetch Customer A's booking details."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust_a, pass_a_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust_b, pass_b_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_a = login(client, cust_a.email, pass_a_c)
    head_b = login(client, cust_b.email, pass_b_c)
    head_admin = login(client, admin.email, pass_admin)

    car_id = create_available_car(client, head_o, head_admin)
    booking_id = make_booking(client, head_a, car_id)

    # Customer B tries to fetch Customer A's booking → 403
    res = client.get(f"/api/v1/customers/me/bookings/{booking_id}", headers=head_b)
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text


def test_customer_cannot_cancel_another_customers_booking(client, db_session):
    """Customer B cannot cancel Customer A's booking."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust_a, pass_a_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust_b, pass_b_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_a = login(client, cust_a.email, pass_a_c)
    head_b = login(client, cust_b.email, pass_b_c)
    head_admin = login(client, admin.email, pass_admin)

    car_id = create_available_car(client, head_o, head_admin)
    booking_id = make_booking(client, head_a, car_id)

    res = client.post(
        f"/api/v1/customers/me/bookings/{booking_id}/cancel",
        json={"cancellation_reason": "Malicious cancel"},
        headers=head_b,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text


def test_customer_bookings_list_only_shows_own(client, db_session):
    """Customer only sees their own bookings in the listing endpoint."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust_a, pass_a_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust_b, pass_b_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_a = login(client, cust_a.email, pass_a_c)
    head_b = login(client, cust_b.email, pass_b_c)
    head_admin = login(client, admin.email, pass_admin)

    car_id = create_available_car(client, head_o, head_admin)
    booking_a_id = make_booking(client, head_a, car_id, days_offset=3)
    # Customer B books a different non-overlapping interval
    booking_b_id = make_booking(client, head_b, car_id, days_offset=10)

    # Customer A's list should only contain their booking
    list_a = client.get("/api/v1/customers/me/bookings", headers=head_a)
    assert list_a.status_code == status.HTTP_200_OK
    ids_a = [item["id"] for item in list_a.json()["items"]]
    assert booking_a_id in ids_a
    assert booking_b_id not in ids_a

    # Customer B's list should only contain their booking
    list_b = client.get("/api/v1/customers/me/bookings", headers=head_b)
    assert list_b.status_code == status.HTTP_200_OK
    ids_b = [item["id"] for item in list_b.json()["items"]]
    assert booking_b_id in ids_b
    assert booking_a_id not in ids_b


# ─────────────────────────────────────────────
# Cross-Owner Isolation
# ─────────────────────────────────────────────

def test_owner_cannot_manage_another_owners_booking(client, db_session):
    """Owner B cannot accept/reject a booking on Owner A's vehicle."""
    db, cleanup_list = db_session
    owner_a, pass_oa = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner_b, pass_ob = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_oa = login(client, owner_a.email, pass_oa)
    head_ob = login(client, owner_b.email, pass_ob)
    head_c = login(client, customer.email, pass_c)
    head_admin = login(client, admin.email, pass_admin)

    # Car belongs to Owner A
    car_id = create_available_car(client, head_oa, head_admin)
    booking_id = make_booking(client, head_c, car_id)

    # Owner B tries to make a decision on Owner A's booking → 403
    res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/decision",
        json={"decision": "ACCEPT"},
        headers=head_ob,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN, res.text


def test_owner_list_only_shows_own_fleet_bookings(client, db_session):
    """Owner only sees bookings for their own fleet vehicles."""
    db, cleanup_list = db_session
    owner_a, pass_oa = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner_b, pass_ob = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_oa = login(client, owner_a.email, pass_oa)
    head_ob = login(client, owner_b.email, pass_ob)
    head_c = login(client, customer.email, pass_c)
    head_admin = login(client, admin.email, pass_admin)

    car_a = create_available_car(client, head_oa, head_admin)
    car_b = create_available_car(client, head_ob, head_admin)

    booking_a_id = make_booking(client, head_c, car_a, days_offset=3)
    booking_b_id = make_booking(client, head_c, car_b, days_offset=3)

    # Owner A's fleet list should not include Owner B's booking
    list_a = client.get("/api/v1/owners/me/bookings", headers=head_oa)
    assert list_a.status_code == status.HTTP_200_OK
    ids_a = [item["id"] for item in list_a.json()["items"]]
    assert booking_a_id in ids_a
    assert booking_b_id not in ids_a


# ─────────────────────────────────────────────
# Admin Oversight
# ─────────────────────────────────────────────

def test_admin_can_view_all_bookings(client, db_session):
    """Admin can see bookings across all customers and owners."""
    db, cleanup_list = db_session
    owner_a, pass_oa = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner_b, pass_ob = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust_a, pass_ca = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust_b, pass_cb = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_oa = login(client, owner_a.email, pass_oa)
    head_ob = login(client, owner_b.email, pass_ob)
    head_ca = login(client, cust_a.email, pass_ca)
    head_cb = login(client, cust_b.email, pass_cb)
    head_admin = login(client, admin.email, pass_admin)

    car_a = create_available_car(client, head_oa, head_admin)
    car_b = create_available_car(client, head_ob, head_admin)

    booking_a_id = make_booking(client, head_ca, car_a, days_offset=3)
    booking_b_id = make_booking(client, head_cb, car_b, days_offset=3)

    # Admin fetches each individually
    res_a = client.get(f"/api/v1/admin/bookings/{booking_a_id}", headers=head_admin)
    assert res_a.status_code == status.HTTP_200_OK, res_a.text
    assert res_a.json()["id"] == booking_a_id

    res_b = client.get(f"/api/v1/admin/bookings/{booking_b_id}", headers=head_admin)
    assert res_b.status_code == status.HTTP_200_OK, res_b.text
    assert res_b.json()["id"] == booking_b_id


def test_admin_list_includes_all_platform_bookings(client, db_session):
    """Admin list endpoint returns bookings from all fleet owners."""
    db, cleanup_list = db_session
    owner_a, pass_oa = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner_b, pass_ob = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_admin = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_oa = login(client, owner_a.email, pass_oa)
    head_ob = login(client, owner_b.email, pass_ob)
    head_c = login(client, customer.email, pass_c)
    head_admin = login(client, admin.email, pass_admin)

    car_a = create_available_car(client, head_oa, head_admin)
    car_b = create_available_car(client, head_ob, head_admin)

    booking_a_id = make_booking(client, head_c, car_a, days_offset=3)
    booking_b_id = make_booking(client, head_c, car_b, days_offset=3)

    list_res = client.get("/api/v1/admin/bookings", headers=head_admin)
    assert list_res.status_code == status.HTTP_200_OK
    all_ids = [item["id"] for item in list_res.json()["items"]]
    assert booking_a_id in all_ids
    assert booking_b_id in all_ids


# ─────────────────────────────────────────────
# Unauthenticated Access
# ─────────────────────────────────────────────

def test_unauthenticated_cannot_create_booking(client, db_session):
    """Booking creation without a token returns 401 Unauthorized."""
    res = client.post(
        "/api/v1/bookings",
        json={
            "car_id": str(uuid.uuid4()),
            "booking_type": "SELF_DRIVE",
            "rental_type": "DAILY",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "pickup_location": "Anywhere",
            "dropoff_location": "Anywhere",
        },
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED, res.text


def test_unauthenticated_cannot_list_customer_bookings(client):
    """Listing customer bookings without a token returns 401 Unauthorized."""
    res = client.get("/api/v1/customers/me/bookings")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED, res.text
