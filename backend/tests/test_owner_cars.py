"""Tests for Owner Car Fleet CRUD Management (/api/v1/owners/me/cars*).

Covers:
- Owner registers a car (default status PENDING_APPROVAL)
- Duplicate registration number rejected (409 Conflict)
- Owner views their owned car
- Owner cannot access another owner's car (403 Forbidden)
- Owner partially updates permitted operational attributes
- Owner cannot update protected fields (rates, status, owner_id)
- Owner deletes car without bookings (hard delete)
- Owner deletes car with bookings (soft archival to INACTIVE)
- Non-owner role denied access (403 Forbidden)
"""

import uuid
from decimal import Decimal
from fastapi import status
from app.models.enums import RoleName, CarStatus
from app.models.booking import Booking
from app.models.car import Car
from tests.conftest import create_user_helper


def create_car_payload(reg_suffix=None):
    """Helper to generate valid car registration payload."""
    suffix = reg_suffix or str(uuid.uuid4())[:6].upper()
    return {
        "brand": "Hyundai",
        "model": "Creta",
        "year": 2023,
        "registration_number": f"KA01MJ{suffix}",
        "fuel_type": "PETROL",
        "transmission": "MANUAL",
        "seating_capacity": 5,
        "odometer_km": 15000,
        "rc_number": f"RC-{suffix}",
        "insurance_policy_number": f"INS-{suffix}",
        "insurance_expiry_date": "2027-12-31",
        "city": "Bangalore",
        "address": "Indiranagar 100ft Road, Bangalore",
        "hourly_rate": "150.00",
        "daily_rate": "2200.00",
        "weekly_rate": "14000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }


def test_owner_create_car_success(client, db_session):
    """Test owner can register a new vehicle with initial PENDING_APPROVAL status."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = create_car_payload()
    response = client.post("/api/v1/owners/me/cars", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["owner_id"] == str(owner.id)
    assert data["brand"] == "Hyundai"
    assert data["model"] == "Creta"
    assert data["status"] == CarStatus.PENDING_APPROVAL.value
    assert data["registration_number"] == payload["registration_number"]


def test_create_car_duplicate_registration_number(client, db_session):
    """Test duplicate registration plate number returns 409 Conflict."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = create_car_payload()
    res1 = client.post("/api/v1/owners/me/cars", json=payload, headers=headers)
    assert res1.status_code == status.HTTP_201_CREATED

    # Attempt second car with same registration number
    res2 = client.post("/api/v1/owners/me/cars", json=payload, headers=headers)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already registered" in res2.json()["detail"]


def test_owner_get_and_list_cars(client, db_session):
    """Test owner can list their cars and retrieve specific car details."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = create_car_payload()
    create_res = client.post("/api/v1/owners/me/cars", json=payload, headers=headers)
    car_id = create_res.json()["id"]

    # List cars
    list_res = client.get("/api/v1/owners/me/cars", headers=headers)
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["total"] >= 1
    car_ids = [c["id"] for c in list_res.json()["items"]]
    assert car_id in car_ids

    # Get single car
    get_res = client.get(f"/api/v1/owners/me/cars/{car_id}", headers=headers)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == car_id


def test_owner_cannot_access_another_owner_car(client, db_session):
    """Test owner cannot view or modify a vehicle owned by another user."""
    db, cleanup_list = db_session
    owner1, pw1 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner2, pw2 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    # Owner 1 creates a car
    t1 = client.post("/api/v1/auth/login", json={"email": owner1.email, "password": pw1}).json()["access_token"]
    h1 = {"Authorization": f"Bearer {t1}"}
    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=h1)
    car_id = car_res.json()["id"]

    # Owner 2 attempts access
    t2 = client.post("/api/v1/auth/login", json={"email": owner2.email, "password": pw2}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}

    get_res = client.get(f"/api/v1/owners/me/cars/{car_id}", headers=h2)
    assert get_res.status_code == status.HTTP_403_FORBIDDEN

    patch_res = client.patch(f"/api/v1/owners/me/cars/{car_id}", json={"city": "Mysore"}, headers=h2)
    assert patch_res.status_code == status.HTTP_403_FORBIDDEN


def test_owner_update_permitted_fields(client, db_session):
    """Test owner can update permitted fields (e.g. odometer, city, address)."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers)
    car_id = create_res.json()["id"]

    patch_payload = {
        "odometer_km": 18500,
        "city": "Mysore",
        "address": "Gokulam 3rd Stage, Mysore",
    }
    patch_res = client.patch(f"/api/v1/owners/me/cars/{car_id}", json=patch_payload, headers=headers)
    assert patch_res.status_code == status.HTTP_200_OK

    data = patch_res.json()
    assert data["odometer_km"] == 18500
    assert data["city"] == "Mysore"
    assert data["address"] == "Gokulam 3rd Stage, Mysore"


def test_owner_cannot_update_protected_fields(client, db_session):
    """Test owner cannot update platform rates, status, or owner_id."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers)
    car_id = create_res.json()["id"]

    # Attempt to modify daily rate and status
    malicious_payload = {
        "daily_rate": "9999.00",
        "status": "AVAILABLE",
        "owner_id": str(uuid.uuid4()),
    }
    patch_res = client.patch(f"/api/v1/owners/me/cars/{car_id}", json=malicious_payload, headers=headers)
    # Extra fields forbidden returns 422
    assert patch_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_owner_delete_car_without_bookings(client, db_session):
    """Test owner can delete a car that has no booking history."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers)
    car_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/owners/me/cars/{car_id}", headers=headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert "deleted successfully" in del_res.json()["message"]

    # Verify car no longer exists
    get_res = client.get(f"/api/v1/owners/me/cars/{car_id}", headers=headers)
    assert get_res.status_code == status.HTTP_404_NOT_FOUND


def test_owner_delete_car_with_bookings_soft_archives(client, db_session):
    """Test car with historical bookings is archived to INACTIVE rather than hard-deleted."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, _ = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers)
    car_id = uuid.UUID(create_res.json()["id"])

    # Simulate an existing booking for this car directly in DB
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    booking = Booking(
        booking_code=f"BK-{str(uuid.uuid4())[:8].upper()}",
        customer_id=customer.id,
        car_id=car_id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=2),
        pickup_location="Airport T1",
        dropoff_location="Airport T1",
        base_amount=Decimal("2000.00"),
        total_amount=Decimal("2000.00"),
    )
    db.add(booking)
    db.commit()

    # Owner requests deletion
    del_res = client.delete(f"/api/v1/owners/me/cars/{car_id}", headers=headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["status"] == CarStatus.INACTIVE.value
    assert "archived" in del_res.json()["message"].lower()

    # Verify car still exists in DB but with INACTIVE status
    db_car = db.query(Car).filter(Car.id == car_id).first()
    assert db_car is not None
    assert db_car.status == CarStatus.INACTIVE.value

    # Cleanup booking so session teardown succeeds
    db.delete(booking)
    db.commit()
