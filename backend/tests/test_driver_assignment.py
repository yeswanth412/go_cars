"""Tests for Driver Assignment to WITH_DRIVER Bookings (Phase 6).

Covers:
- Admin can assign an approved & online driver → 200
- Owner can assign a driver to their own fleet booking → 200
- Assigning an unverified driver → 400
- Assigning an offline driver → 400
- Assigning a driver with an overlapping trip → 409
- Driver can view their assigned trips via /drivers/me/trips
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from app.models.enums import (
    RoleName, CarStatus, BookingType, RentalType,
    DriverVerificationStatus, DriverDutyStatus,
)
from tests.conftest import create_user_helper


def login(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == status.HTTP_200_OK, f"Login failed for {email}: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_available_car(client, owner_headers, admin_headers, city="Bangalore"):
    suffix = str(uuid.uuid4())[:6].upper()
    payload = {
        "brand": "Honda",
        "model": "City",
        "year": 2022,
        "registration_number": f"KA03DA{suffix}",
        "fuel_type": "PETROL",
        "transmission": "MANUAL",
        "seating_capacity": 5,
        "odometer_km": 8000,
        "rc_number": f"RC-DA-{suffix}",
        "insurance_policy_number": f"INS-DA-{suffix}",
        "insurance_expiry_date": "2028-06-30",
        "city": city,
        "address": "Koramangala, Bangalore",
        "hourly_rate": "100.00",
        "daily_rate": "1200.00",
        "weekly_rate": "7500.00",
        "is_self_drive_allowed": False,
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


def approve_driver(client, db, driver_user, admin_headers):
    """Approve driver verification via a fresh DB session.

    Ensures DriverProfile exists in the database before updating to APPROVED,
    guaranteeing durability and visibility across all application sessions.
    """
    from datetime import date, timedelta
    from app.core.database import SessionLocal
    from app.models.user import DriverProfile
    from app.models.enums import DriverVerificationStatus, DriverDutyStatus

    fresh = SessionLocal()
    try:
        prof = fresh.query(DriverProfile).filter_by(user_id=driver_user.id).first()
        if not prof:
            prof = DriverProfile(
                user_id=driver_user.id,
                license_number=f"DL-{str(driver_user.id).replace('-', '')[:12].upper()}",
                license_expiry_date=date.today() + timedelta(days=365 * 3),
                experience_years=3,
                verification_status=DriverVerificationStatus.APPROVED.value,
                duty_status=DriverDutyStatus.OFFLINE.value,
                current_city="Bangalore",
            )
            fresh.add(prof)
        else:
            prof.verification_status = DriverVerificationStatus.APPROVED.value
        fresh.commit()
    finally:
        fresh.close()


def create_with_driver_booking(client, customer_headers, car_id, days_offset=3):
    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(days=days_offset)).isoformat()
    end_time = (now + timedelta(days=days_offset + 2)).isoformat()
    payload = {
        "car_id": car_id,
        "booking_type": BookingType.WITH_DRIVER.value,
        "rental_type": RentalType.DAILY.value,
        "start_time": start_time,
        "end_time": end_time,
        "pickup_location": "Koramangala 5th Block",
        "dropoff_location": "MG Road",
    }
    res = client.post("/api/v1/bookings", json=payload, headers=customer_headers)
    assert res.status_code == status.HTTP_201_CREATED, res.text
    return res.json()["id"]


def test_admin_can_assign_approved_online_driver(client, db_session):
    """Admin successfully assigns an approved and online driver to a WITH_DRIVER booking."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_d = login(client, driver_user.email, pass_d)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, city="Bangalore")

    # Admin approves driver
    approve_driver(client, db, driver_user, head_a)

    # Driver updates city to match car city and goes ONLINE
    client.patch(
        "/api/v1/drivers/me/profile",
        json={"current_city": "Bangalore"},
        headers=head_d,
    )
    online_res = client.patch(
        "/api/v1/drivers/me/profile",
        json={"duty_status": DriverDutyStatus.ONLINE.value},
        headers=head_d,
    )
    assert online_res.status_code == status.HTTP_200_OK, online_res.text

    booking_id = create_with_driver_booking(client, head_c, car_id)

    # Admin assigns driver
    assign_res = client.post(
        f"/api/v1/admin/bookings/{booking_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )
    assert assign_res.status_code == status.HTTP_200_OK, assign_res.text
    data = assign_res.json()
    assert data["driver_id"] == str(driver_user.id)


def test_owner_can_assign_driver_to_own_fleet_booking(client, db_session):
    """Fleet owner can assign a driver to a booking on their own vehicle."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_d = login(client, driver_user.email, pass_d)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, city="Bangalore")
    approve_driver(client, db, driver_user, head_a)

    client.patch("/api/v1/drivers/me/profile", json={"current_city": "Bangalore"}, headers=head_d)
    client.patch("/api/v1/drivers/me/profile", json={"duty_status": DriverDutyStatus.ONLINE.value}, headers=head_d)

    booking_id = create_with_driver_booking(client, head_c, car_id)

    # Owner assigns driver to booking on their car
    assign_res = client.post(
        f"/api/v1/owners/me/bookings/{booking_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_o,
    )
    assert assign_res.status_code == status.HTTP_200_OK, assign_res.text
    assert assign_res.json()["driver_id"] == str(driver_user.id)


def test_assigning_unverified_driver_rejected(client, db_session):
    """Assigning a PENDING (unverified) driver returns 400 Bad Request."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)
    head_d = login(client, driver_user.email, pass_d)

    # Initialize the driver's profile so it exists in PENDING verification status
    init_res = client.get("/api/v1/drivers/me/profile", headers=head_d)
    assert init_res.status_code == status.HTTP_200_OK

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_with_driver_booking(client, head_c, car_id)

    # Driver is still PENDING — do NOT call approve_driver
    assign_res = client.post(
        f"/api/v1/admin/bookings/{booking_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )
    assert assign_res.status_code == status.HTTP_400_BAD_REQUEST, assign_res.text
    assert "not approved" in assign_res.json()["detail"].lower()


def test_assigning_offline_driver_rejected(client, db_session):
    """Assigning an OFFLINE driver (even if approved) returns 400 Bad Request."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a)
    booking_id = create_with_driver_booking(client, head_c, car_id)

    # Approve driver but leave duty_status = OFFLINE (default)
    approve_driver(client, db, driver_user, head_a)

    assign_res = client.post(
        f"/api/v1/admin/bookings/{booking_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )
    assert assign_res.status_code == status.HTTP_400_BAD_REQUEST, assign_res.text
    assert "not currently available" in assign_res.json()["detail"].lower()


def test_assigning_driver_with_overlap_rejected(client, db_session):
    """Assigning a driver who already has a conflicting trip returns 409 Conflict."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    cust1, pass_c1 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    cust2, pass_c2 = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c1 = login(client, cust1.email, pass_c1)
    head_c2 = login(client, cust2.email, pass_c2)
    head_d = login(client, driver_user.email, pass_d)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, city="Bangalore")
    approve_driver(client, db, driver_user, head_a)
    client.patch("/api/v1/drivers/me/profile", json={"current_city": "Bangalore"}, headers=head_d)
    client.patch("/api/v1/drivers/me/profile", json={"duty_status": DriverDutyStatus.ONLINE.value}, headers=head_d)

    # Booking 1: days 3–5
    booking1_id = create_with_driver_booking(client, head_c1, car_id, days_offset=3)

    # Assign driver to booking 1
    assign1_res = client.post(
        f"/api/v1/admin/bookings/{booking1_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )
    assert assign1_res.status_code == status.HTTP_200_OK, assign1_res.text

    # Create a second overlapping booking on a different car (same owner, same dates)
    suffix = str(uuid.uuid4())[:6].upper()
    payload2 = {
        "brand": "Maruti",
        "model": "Swift",
        "year": 2021,
        "registration_number": f"KA03DA{suffix}",
        "fuel_type": "PETROL",
        "transmission": "MANUAL",
        "seating_capacity": 5,
        "odometer_km": 3000,
        "rc_number": f"RC-DA2-{suffix}",
        "insurance_policy_number": f"INS-DA2-{suffix}",
        "insurance_expiry_date": "2028-06-30",
        "city": "Bangalore",
        "address": "JP Nagar",
        "hourly_rate": "100.00",
        "daily_rate": "1200.00",
        "weekly_rate": "7500.00",
        "is_self_drive_allowed": False,
        "is_driver_allowed": True,
    }
    car2_res = client.post("/api/v1/owners/me/cars", json=payload2, headers=head_o)
    car2_id = car2_res.json()["id"]
    client.patch(f"/api/v1/admin/cars/{car2_id}/approval", json={"status": CarStatus.AVAILABLE.value}, headers=head_a)

    booking2_id = create_with_driver_booking(client, head_c2, car2_id, days_offset=3)

    # Trying to assign the same driver to the overlapping booking → 409
    assign2_res = client.post(
        f"/api/v1/admin/bookings/{booking2_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )
    assert assign2_res.status_code == status.HTTP_409_CONFLICT, assign2_res.text


def test_driver_can_view_assigned_trips(client, db_session):
    """Driver can view their assigned trips via /api/v1/drivers/me/trips."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])
    driver_user, pass_d = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    head_o = login(client, owner.email, pass_o)
    head_c = login(client, customer.email, pass_c)
    head_d = login(client, driver_user.email, pass_d)
    head_a = login(client, admin.email, pass_a)

    car_id = create_available_car(client, head_o, head_a, city="Bangalore")
    approve_driver(client, db, driver_user, head_a)
    client.patch("/api/v1/drivers/me/profile", json={"current_city": "Bangalore"}, headers=head_d)
    client.patch("/api/v1/drivers/me/profile", json={"duty_status": DriverDutyStatus.ONLINE.value}, headers=head_d)

    booking_id = create_with_driver_booking(client, head_c, car_id)

    # Assign driver
    client.post(
        f"/api/v1/admin/bookings/{booking_id}/assign-driver",
        json={"driver_id": str(driver_user.id)},
        headers=head_a,
    )

    # Driver views their trips
    trips_res = client.get("/api/v1/drivers/me/trips", headers=head_d)
    assert trips_res.status_code == status.HTTP_200_OK, trips_res.text
    data = trips_res.json()
    assert data["total"] >= 1
    booking_ids = [item["id"] for item in data["items"]]
    assert booking_id in booking_ids
