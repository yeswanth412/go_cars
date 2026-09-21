"""Tests for Admin Car Fleet Management & Public Car Search (Phase 5)."""

import uuid
import pytest
from fastapi import status
from app.models.enums import RoleName, CarStatus, FuelType, TransmissionType
from tests.conftest import create_user_helper


def create_car_payload(city="Bangalore", fuel_type="PETROL", daily_rate="2000.00", seating=5):
    suffix = str(uuid.uuid4())[:6].upper()
    return {
        "brand": "Hyundai",
        "model": "Verna",
        "year": 2023,
        "registration_number": f"KA03ADM{suffix}",
        "fuel_type": fuel_type,
        "transmission": "AUTOMATIC",
        "seating_capacity": seating,
        "odometer_km": 10000,
        "rc_number": f"RC-ADM-{suffix}",
        "insurance_policy_number": f"INS-ADM-{suffix}",
        "insurance_expiry_date": "2027-05-20",
        "city": city,
        "address": "MG Road, Central",
        "hourly_rate": "150.00",
        "daily_rate": daily_rate,
        "weekly_rate": "13000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }


def test_admin_car_approval_and_status_transitions(client, db_session):
    """Test admin listing cars, approving, rejecting, and updating operational status."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}
    login_a = client.post("/api/v1/auth/login", json={"email": admin.email, "password": pass_a})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Owner creates 2 cars (both default to PENDING_APPROVAL)
    car1_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers_o)
    car1_id = car1_res.json()["id"]
    car2_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers_o)
    car2_id = car2_res.json()["id"]

    # 1. Admin lists cars with status filter
    pending_list = client.get("/api/v1/admin/cars?status=PENDING_APPROVAL", headers=headers_a)
    assert pending_list.status_code == status.HTTP_200_OK
    pending_ids = [c["id"] for c in pending_list.json()["items"]]
    assert car1_id in pending_ids
    assert car2_id in pending_ids

    # 2. Admin inspects car details
    detail_res = client.get(f"/api/v1/admin/cars/{car1_id}", headers=headers_a)
    assert detail_res.status_code == status.HTTP_200_OK
    assert detail_res.json()["rc_number"] is not None  # Admin can inspect sensitive RC info

    # 3. Admin approves car 1 -> status becomes AVAILABLE
    approve_res = client.patch(
        f"/api/v1/admin/cars/{car1_id}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=headers_a,
    )
    assert approve_res.status_code == status.HTTP_200_OK
    assert approve_res.json()["status"] == CarStatus.AVAILABLE.value

    # 4. Admin rejects car 2 -> status becomes REJECTED
    reject_res = client.patch(
        f"/api/v1/admin/cars/{car2_id}/approval",
        json={"status": CarStatus.REJECTED.value, "rejection_reason": "Fitness certificate expired"},
        headers=headers_a,
    )
    assert reject_res.status_code == status.HTTP_200_OK
    assert reject_res.json()["status"] == CarStatus.REJECTED.value

    # 5. Admin updates car 1 status to MAINTENANCE
    maint_res = client.patch(
        f"/api/v1/admin/cars/{car1_id}/status",
        json={"status": CarStatus.MAINTENANCE.value},
        headers=headers_a,
    )
    assert maint_res.status_code == status.HTTP_200_OK
    assert maint_res.json()["status"] == CarStatus.MAINTENANCE.value


def test_public_car_search_and_privacy_sanitization(client, db_session):
    """Test public search filters, isolation of unapproved cars, and privacy data masking."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}
    login_a = client.post("/api/v1/auth/login", json={"email": admin.email, "password": pass_a})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Car A: in "Hyderabad", DIESEL, daily_rate 2500 -> will be APPROVED
    car_a = client.post(
        "/api/v1/owners/me/cars",
        json=create_car_payload(city="Hyderabad", fuel_type="DIESEL", daily_rate="2500.00"),
        headers=headers_o,
    ).json()
    client.patch(
        f"/api/v1/admin/cars/{car_a['id']}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=headers_a,
    )

    # Car B: in "Bangalore", PETROL, daily_rate 1500 -> will be APPROVED
    car_b = client.post(
        "/api/v1/owners/me/cars",
        json=create_car_payload(city="Bangalore", fuel_type="PETROL", daily_rate="1500.00"),
        headers=headers_o,
    ).json()
    client.patch(
        f"/api/v1/admin/cars/{car_b['id']}/approval",
        json={"status": CarStatus.AVAILABLE.value},
        headers=headers_a,
    )

    # Car C: in "Bangalore", PETROL -> remains PENDING_APPROVAL
    car_c = client.post(
        "/api/v1/owners/me/cars",
        json=create_car_payload(city="Bangalore", fuel_type="PETROL", daily_rate="1200.00"),
        headers=headers_o,
    ).json()

    # 1. Unauthenticated public search for city=Bangalore
    pub_res = client.get("/api/v1/cars?city=Bangalore")
    assert pub_res.status_code == status.HTTP_200_OK
    found_ids = [c["id"] for c in pub_res.json()["items"]]
    assert car_b["id"] in found_ids
    # Car C (PENDING_APPROVAL) must NEVER appear in public search
    assert car_c["id"] not in found_ids
    # Car A (Hyderabad) must not appear in Bangalore search
    assert car_a["id"] not in found_ids

    # 2. Filter by fuel_type=DIESEL
    diesel_res = client.get("/api/v1/cars?fuel_type=DIESEL")
    assert diesel_res.status_code == status.HTTP_200_OK
    diesel_ids = [c["id"] for c in diesel_res.json()["items"]]
    assert car_a["id"] in diesel_ids
    assert car_b["id"] not in diesel_ids

    # 3. Filter by max_daily_rate=2000
    price_res = client.get("/api/v1/cars?max_daily_rate=2000.00")
    assert price_res.status_code == status.HTTP_200_OK
    price_ids = [c["id"] for c in price_res.json()["items"]]
    assert car_b["id"] in price_ids
    assert car_a["id"] not in price_ids

    # 4. Public car details - verify sensitive data is NOT exposed
    detail_res = client.get(f"/api/v1/cars/{car_b['id']}")
    assert detail_res.status_code == status.HTTP_200_OK
    pub_detail = detail_res.json()
    assert "rc_number" not in pub_detail
    assert "insurance_policy_number" not in pub_detail
    assert "insurance_expiry_date" not in pub_detail
    assert "documents" not in pub_detail
    assert "owner_id" not in pub_detail

    # 5. Public car details for unapproved car -> 404
    c_detail_res = client.get(f"/api/v1/cars/{car_c['id']}")
    assert c_detail_res.status_code == status.HTTP_404_NOT_FOUND
