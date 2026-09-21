"""Tests for Car Blackout Period Management (Phase 5)."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from app.models.enums import RoleName, BlackoutReason
from tests.conftest import create_user_helper


def create_car_payload():
    suffix = str(uuid.uuid4())[:6].upper()
    return {
        "brand": "Honda",
        "model": "City",
        "year": 2023,
        "registration_number": f"KA05BLK{suffix}",
        "fuel_type": "PETROL",
        "transmission": "AUTOMATIC",
        "seating_capacity": 5,
        "odometer_km": 12000,
        "rc_number": f"RC-BLK-{suffix}",
        "insurance_policy_number": f"INS-BLK-{suffix}",
        "insurance_expiry_date": "2027-08-30",
        "city": "Bangalore",
        "address": "HSR Layout Sector 1",
        "hourly_rate": "180.00",
        "daily_rate": "2400.00",
        "weekly_rate": "15000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }


def test_blackout_period_lifecycle_and_overlap_detection(client, db_session):
    """Test creating blackout periods, overlap conflict prevention, listing, and deletion."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}

    # 1. Create car
    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers_o)
    car_id = car_res.json()["id"]

    now = datetime.now(timezone.utc)
    t1_start = (now + timedelta(days=5)).isoformat()
    t1_end = (now + timedelta(days=8)).isoformat()

    # 2. Add valid blackout window
    blk1_payload = {
        "start_time": t1_start,
        "end_time": t1_end,
        "reason": BlackoutReason.MAINTENANCE.value,
    }
    blk1_res = client.post(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", json=blk1_payload, headers=headers_o)
    assert blk1_res.status_code == status.HTTP_201_CREATED
    blk1_data = blk1_res.json()
    assert blk1_data["reason"] == BlackoutReason.MAINTENANCE.value
    blk1_id = blk1_data["id"]

    # 3. Test invalid time window: end_time <= start_time -> 422 Unprocessable
    invalid_time_payload = {
        "start_time": t1_end,
        "end_time": t1_start,
        "reason": BlackoutReason.OWNER_USE.value,
    }
    inv_res = client.post(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", json=invalid_time_payload, headers=headers_o)
    assert inv_res.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, 422]

    # 4. Test overlapping blackout window -> 409 Conflict
    # Overlapping window: day 6 to day 10 (overlaps days 5-8)
    overlap_payload = {
        "start_time": (now + timedelta(days=6)).isoformat(),
        "end_time": (now + timedelta(days=10)).isoformat(),
        "reason": BlackoutReason.OWNER_USE.value,
    }
    overlap_res = client.post(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", json=overlap_payload, headers=headers_o)
    assert overlap_res.status_code == status.HTTP_409_CONFLICT
    assert "overlap" in overlap_res.json()["detail"].lower()

    # 5. List blackout periods
    list_res = client.get(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", headers=headers_o)
    assert list_res.status_code == status.HTTP_200_OK
    assert len(list_res.json()) == 1

    # 6. Delete blackout period
    del_res = client.delete(f"/api/v1/owners/me/cars/{car_id}/blackout-periods/{blk1_id}", headers=headers_o)
    assert del_res.status_code == status.HTTP_200_OK

    # 7. Verify deletion
    list_after = client.get(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", headers=headers_o)
    assert len(list_after.json()) == 0


def test_cross_owner_blackout_forbidden(client, db_session):
    """Test other owners cannot modify blackout periods."""
    db, cleanup_list = db_session
    owner1, pass1 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner2, pass2 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login1 = client.post("/api/v1/auth/login", json={"email": owner1.email, "password": pass1})
    headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}
    login2 = client.post("/api/v1/auth/login", json={"email": owner2.email, "password": pass2})
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers1)
    car_id = car_res.json()["id"]

    now = datetime.now(timezone.utc)
    blk_payload = {
        "start_time": (now + timedelta(days=2)).isoformat(),
        "end_time": (now + timedelta(days=4)).isoformat(),
        "reason": BlackoutReason.OWNER_USE.value,
    }
    res = client.post(f"/api/v1/owners/me/cars/{car_id}/blackout-periods", json=blk_payload, headers=headers2)
    assert res.status_code == status.HTTP_403_FORBIDDEN
