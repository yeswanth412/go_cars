"""Tests for Customer Profile Management (/api/v1/customers/me/profile).

Covers:
- View customer rental profile
- Partial update permitted attributes (emergency contact, driving license)
- Prohibition of customer self-verification (is_license_verified cannot be set)
- Rejection of invalid profile data
- Authorization rejection for users lacking CUSTOMER role (403 Forbidden)
"""

from datetime import date
from fastapi import status
from app.models.enums import RoleName
from tests.conftest import create_user_helper


def test_get_customer_profile_success(client, db_session):
    """Test customer can retrieve their rental profile."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/customers/me/profile", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["is_license_verified"] is False


def test_patch_customer_profile_permitted_fields(client, db_session):
    """Test customer can update permitted fields like emergency contact and license."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "driving_license_number": "DL-KA01-20240001",
        "license_expiry_date": "2030-12-31",
        "emergency_contact_name": "Emergency Jane",
        "emergency_contact_phone": "9998887776",
    }
    response = client.patch("/api/v1/customers/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["driving_license_number"] == "DL-KA01-20240001"
    assert data["license_expiry_date"] == "2030-12-31"
    assert data["emergency_contact_name"] == "Emergency Jane"
    assert data["emergency_contact_phone"] == "9998887776"
    assert data["is_license_verified"] is False


def test_customer_cannot_self_verify(client, db_session):
    """Test that customer cannot self-verify their driving license."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to inject is_license_verified
    payload = {
        "is_license_verified": True,
    }
    response = client.patch("/api/v1/customers/me/profile", json=payload, headers=headers)
    # Extra field forbidden produces 422 Unprocessable Entity
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_non_customer_denied_access(client, db_session):
    """Test user without CUSTOMER role is denied access with 403 Forbidden."""
    db, cleanup_list = db_session
    # User with OWNER role only
    user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/customers/me/profile", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Requires role: CUSTOMER" in response.json()["detail"]
