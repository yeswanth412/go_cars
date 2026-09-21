"""Tests for Commercial Driver Profile Management (/api/v1/drivers/me/profile).

Covers:
- Driver can view own profile
- Driver can update permitted fields (experience, city)
- Driver cannot self-verify (verification_status is rejected)
- Unverified driver cannot go ONLINE (403 Forbidden)
- Negative experience rejected (422)
- Unauthorized users without DRIVER role denied (403 Forbidden)
"""

from fastapi import status
from app.models.enums import RoleName
from tests.conftest import create_user_helper


def test_driver_can_view_own_profile(client, db_session):
    """Test authenticated user with DRIVER role can view their driver profile."""
    db, cleanup_list = db_session
    driver_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": driver_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/drivers/me/profile", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["user_id"] == str(driver_user.id)
    assert data["verification_status"] == "PENDING"
    assert data["duty_status"] == "OFFLINE"


def test_driver_can_update_permitted_fields(client, db_session):
    """Test driver can update permitted attributes (city, experience)."""
    db, cleanup_list = db_session
    driver_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": driver_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "experience_years": 5,
        "current_city": "Bangalore",
    }
    response = client.patch("/api/v1/drivers/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["experience_years"] == 5
    assert data["current_city"] == "Bangalore"


def test_driver_cannot_self_verify(client, db_session):
    """Test driver cannot self-verify ('verification_status' cannot be altered by driver)."""
    db, cleanup_list = db_session
    driver_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": driver_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "verification_status": "APPROVED",
    }
    response = client.patch("/api/v1/drivers/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_unverified_driver_cannot_go_online(client, db_session):
    """Test unverified driver (PENDING) is forbidden from setting duty status to ONLINE."""
    db, cleanup_list = db_session
    driver_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": driver_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "duty_status": "ONLINE",
    }
    response = client.patch("/api/v1/drivers/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Unverified drivers cannot go ONLINE" in response.json()["detail"]


def test_negative_experience_years_rejected(client, db_session):
    """Test negative experience_years fails validation."""
    db, cleanup_list = db_session
    driver_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.DRIVER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": driver_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "experience_years": -2,
    }
    response = client.patch("/api/v1/drivers/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_unauthorized_user_denied_driver_profile(client, db_session):
    """Test user without DRIVER role is denied with 403 Forbidden."""
    db, cleanup_list = db_session
    cust_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": cust_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/drivers/me/profile", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Requires role: DRIVER" in response.json()["detail"]
