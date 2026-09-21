"""Tests for Car Image Management (Phase 5)."""

import uuid
import pytest
from fastapi import status
from app.models.enums import RoleName
from tests.conftest import create_user_helper


def create_car_payload():
    suffix = str(uuid.uuid4())[:6].upper()
    return {
        "brand": "Toyota",
        "model": "Innova Crysta",
        "year": 2023,
        "registration_number": f"KA53IMG{suffix}",
        "fuel_type": "DIESEL",
        "transmission": "AUTOMATIC",
        "seating_capacity": 7,
        "odometer_km": 20000,
        "rc_number": f"RC-IMG-{suffix}",
        "insurance_policy_number": f"INS-IMG-{suffix}",
        "insurance_expiry_date": "2027-12-31",
        "city": "Bangalore",
        "address": "Outer Ring Road, Marathahalli",
        "hourly_rate": "250.00",
        "daily_rate": "3500.00",
        "weekly_rate": "22000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }


def test_car_image_upload_and_primary_toggle(client, db_session):
    """Test owner uploading images and primary image flag management."""
    db, cleanup_list = db_session
    owner, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post("/api/v1/auth/login", json={"email": owner.email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create car
    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers)
    car_id = car_res.json()["id"]

    # 1. Add first image as primary
    img1_payload = {
        "image_url": "https://storage.gocars.com/cars/toyota-front.jpg",
        "is_primary": True,
        "caption": "Front angle view",
    }
    img1_res = client.post(f"/api/v1/owners/me/cars/{car_id}/images", json=img1_payload, headers=headers)
    assert img1_res.status_code == status.HTTP_201_CREATED
    img1_data = img1_res.json()
    assert img1_data["is_primary"] is True
    assert img1_data["image_url"] == img1_payload["image_url"]
    img1_id = img1_data["id"]

    # 2. Add second image also as primary -> should automatically unmark first image
    img2_payload = {
        "image_url": "https://storage.gocars.com/cars/toyota-side.jpg",
        "is_primary": True,
        "caption": "Side view",
    }
    img2_res = client.post(f"/api/v1/owners/me/cars/{car_id}/images", json=img2_payload, headers=headers)
    assert img2_res.status_code == status.HTTP_201_CREATED
    img2_data = img2_res.json()
    assert img2_data["is_primary"] is True
    img2_id = img2_data["id"]

    # 3. List images to verify primary status
    list_res = client.get(f"/api/v1/owners/me/cars/{car_id}/images", headers=headers)
    assert list_res.status_code == status.HTTP_200_OK
    images = list_res.json()
    assert len(images) == 2

    # Verify first image is now is_primary = False
    img1_fetched = next(i for i in images if i["id"] == img1_id)
    img2_fetched = next(i for i in images if i["id"] == img2_id)
    assert img1_fetched["is_primary"] is False
    assert img2_fetched["is_primary"] is True

    # 4. Delete an image
    del_res = client.delete(f"/api/v1/owners/me/cars/{car_id}/images/{img1_id}", headers=headers)
    assert del_res.status_code == status.HTTP_200_OK

    # Verify count is now 1
    list_after = client.get(f"/api/v1/owners/me/cars/{car_id}/images", headers=headers)
    assert len(list_after.json()) == 1


def test_unauthorized_image_operations(client, db_session):
    """Test non-owners or other owners cannot add or delete images."""
    db, cleanup_list = db_session
    owner1, pass1 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    owner2, pass2 = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    customer, pass_c = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login1 = client.post("/api/v1/auth/login", json={"email": owner1.email, "password": pass1})
    headers1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    login2 = client.post("/api/v1/auth/login", json={"email": owner2.email, "password": pass2})
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    login_c = client.post("/api/v1/auth/login", json={"email": customer.email, "password": pass_c})
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}

    # Owner 1 creates car
    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers1)
    car_id = car_res.json()["id"]

    # Customer tries to add image -> 403 Forbidden
    img_payload = {"image_url": "https://storage.gocars.com/fake.jpg", "is_primary": False}
    res_c = client.post(f"/api/v1/owners/me/cars/{car_id}/images", json=img_payload, headers=headers_c)
    assert res_c.status_code == status.HTTP_403_FORBIDDEN

    # Owner 2 tries to add image to Owner 1's car -> 403 Forbidden
    res2 = client.post(f"/api/v1/owners/me/cars/{car_id}/images", json=img_payload, headers=headers2)
    assert res2.status_code == status.HTTP_403_FORBIDDEN
