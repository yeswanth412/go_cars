"""Tests for Booking Creation & Platform Pricing Calculation (Phase 6)."""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from app.models.enums import RoleName, CarStatus, BookingType, RentalType, BookingStatus
from tests.conftest import create_user_helper


def create_available_car(client, owner_headers, admin_headers, is_self_drive=True, is_driver=True):
    suffix = str(uuid.uuid4())[:6].upper()
    payload = {
        "brand": "Hyundai",
        "model": "Creta",
        "year": 2023,
        "registration_number": f"KA01BK{suffix}",
        "fuel_type": "PETROL",
        "transmission": "AUTOMATIC",
        "seating_capacity": 5,
        "odometer_km": 10000,
        "rc_number": f"RC-BK-{suffix}",
        "insurance_policy_number": f"INS-BK-{suffix}",
        "insurance_expiry_date": "2027-12-31",
        "city": "Bangalore",
        "address": "Indiranagar 100ft Road",
        "hourly_rate": "200.00",
        "daily_rate": "2400.00",
        "weekly_rate": "15000.00",
        "is_self_drive_allowed": is_self_drive,
        "is_driver_allowed": is_driver,
    }
    car_res = client.post("/api/v1/owners/me/cars", json=payload, headers=owner_headers)
    car_id = car_res.json()["id"]

    # Admin approves car to AVAILABLE
    client.patch(
        f"/api/v1/admin/cars/{car_id}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=admin_headers,
    )
    return car_id


def test_customer_create_self_drive_booking_with_pricing_snapshot(client, db_session):
    """Test creating self-drive booking and verifying exact platform pricing snapshot."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}
    login_c = client.post("/api/v1/auth/login", json={"email": customer.email, "password": pass_c})
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}
    login_a = client.post("/api/v1/auth/login", json={"email": admin.email, "password": pass_a})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    car_id = create_available_car(client, headers_o, headers_a)

    now = datetime.now(timezone.utc)
    # Exactly 2 days rental
    start_time = (now + timedelta(days=2)).isoformat()
    end_time = (now + timedelta(days=4)).isoformat()

    # 1. Preview estimate
    est_payload = {
        "car_id": car_id,
        "booking_type": BookingType.SELF_DRIVE.value,
        "rental_type": RentalType.DAILY.value,
        "start_time": start_time,
        "end_time": end_time,
    }
    est_res = client.post("/api/v1/bookings/estimate-price", json=est_payload, headers=headers_c)
    assert est_res.status_code == status.HTTP_200_OK
    est_data = est_res.json()
    assert est_data["billable_units"] == 2
    # 2 days * 2400 = 4800 base
    assert Decimal(est_data["base_amount"]) == Decimal("4800.00")
    assert Decimal(est_data["driver_charge"]) == Decimal("0.00")
    # Platform fee = 5% of 4800 = 240
    assert Decimal(est_data["platform_fee"]) == Decimal("240.00")
    # Tax = 18% of (4800 + 240) = 907.20
    assert Decimal(est_data["tax_amount"]) == Decimal("907.20")
    assert Decimal(est_data["security_deposit"]) == Decimal("2000.00")
    # Total = 4800 + 240 + 907.20 + 2000 = 7947.20
    assert Decimal(est_data["total_amount"]) == Decimal("7947.20")

    # 2. Create actual booking
    book_payload = {
        "car_id": car_id,
        "booking_type": BookingType.SELF_DRIVE.value,
        "rental_type": RentalType.DAILY.value,
        "start_time": start_time,
        "end_time": end_time,
        "pickup_location": "Airport Terminal 2",
        "dropoff_location": "Airport Terminal 2",
    }
    res = client.post("/api/v1/bookings", json=book_payload, headers=headers_c)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["status"] == BookingStatus.PENDING_PAYMENT.value
    assert data["booking_code"].startswith("BK-")
    assert Decimal(data["total_amount"]) == Decimal("7947.20")
    assert Decimal(data["base_amount"]) == Decimal("4800.00")
    assert Decimal(data["security_deposit"]) == Decimal("2000.00")


def test_customer_create_with_driver_booking_pricing(client, db_session):
    """Test with-driver booking includes correct driver charge and platform calculations."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    headers_o = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': owner.email, 'password': pass_o}).json()['access_token']}"}
    headers_c = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': customer.email, 'password': pass_c}).json()['access_token']}"}
    headers_a = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': admin.email, 'password': pass_a}).json()['access_token']}"}

    car_id = create_available_car(client, headers_o, headers_a)

    now = datetime.now(timezone.utc)
    # 1 day with driver
    start_time = (now + timedelta(days=5)).isoformat()
    end_time = (now + timedelta(days=6)).isoformat()

    book_payload = {
        "car_id": car_id,
        "booking_type": BookingType.WITH_DRIVER.value,
        "rental_type": RentalType.DAILY.value,
        "start_time": start_time,
        "end_time": end_time,
        "pickup_location": "Indiranagar 100ft Rd",
        "dropoff_location": "Whitefield",
    }
    res = client.post("/api/v1/bookings", json=book_payload, headers=headers_c)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    # 1 day base = 2400, driver = 500
    assert Decimal(data["base_amount"]) == Decimal("2400.00")
    assert Decimal(data["driver_charge"]) == Decimal("500.00")
    # Subtotal = 2900. Platform fee 5% = 145.00
    assert Decimal(data["platform_fee"]) == Decimal("145.00")
    # Tax = 18% of (2900 + 145) = 548.10
    assert Decimal(data["tax_amount"]) == Decimal("548.10")
    # Total = 2900 + 145 + 548.10 + 2000 = 5593.10
    assert Decimal(data["total_amount"]) == Decimal("5593.10")


def test_booking_validation_errors(client, db_session):
    """Test validation rejections for invalid times, unapproved cars, and disallowed modes."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    headers_o = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': owner.email, 'password': pass_o}).json()['access_token']}"}
    headers_c = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': customer.email, 'password': pass_c}).json()['access_token']}"}
    headers_a = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': admin.email, 'password': pass_a}).json()['access_token']}"}

    # Car 1: Chauffeur only (is_self_drive_allowed = False)
    car1_id = create_available_car(client, headers_o, headers_a, is_self_drive=False, is_driver=True)

    now = datetime.now(timezone.utc)
    future_start = (now + timedelta(days=2)).isoformat()
    future_end = (now + timedelta(days=3)).isoformat()
    past_start = (now - timedelta(days=1)).isoformat()

    # 1. Past start_time -> 422
    past_res = client.post(
        "/api/v1/bookings",
        json={"car_id": car1_id, "start_time": past_start, "end_time": future_end, "pickup_location": "A", "dropoff_location": "B"},
        headers=headers_c,
    )
    assert past_res.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, 422]

    # 2. end_time <= start_time -> 422
    inv_window_res = client.post(
        "/api/v1/bookings",
        json={"car_id": car1_id, "start_time": future_end, "end_time": future_start, "pickup_location": "A", "dropoff_location": "B"},
        headers=headers_c,
    )
    assert inv_window_res.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, 422]

    # 3. Disallowed mode: self-drive requested on car1 -> 400
    mode_res = client.post(
        "/api/v1/bookings",
        json={"car_id": car1_id, "booking_type": "SELF_DRIVE", "start_time": future_start, "end_time": future_end, "pickup_location": "Airport T1", "dropoff_location": "Indiranagar 100ft"},
        headers=headers_c,
    )
    assert mode_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "self-drive" in mode_res.json()["detail"].lower()

    # 4. Owner cannot book their own car -> 400
    owner_as_customer, pass_oc = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value, RoleName.CUSTOMER.value])
    headers_oc = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': owner_as_customer.email, 'password': pass_oc}).json()['access_token']}"}
    own_car_id = create_available_car(client, headers_oc, headers_a)

    own_book_res = client.post(
        "/api/v1/bookings",
        json={"car_id": own_car_id, "booking_type": "SELF_DRIVE", "start_time": future_start, "end_time": future_end, "pickup_location": "Airport T1", "dropoff_location": "Indiranagar 100ft"},
        headers=headers_oc,
    )
    assert own_book_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "own" in own_book_res.json()["detail"].lower()
