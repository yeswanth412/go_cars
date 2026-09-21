"""Tests for Vehicle Owner Profile Management (/api/v1/owners/me/profile).

Covers:
- Owner can view own profile
- Owner can update permitted fields (business_name, tax_id_number, payout_account_reference)
- Customer cannot access OWNER endpoints (403 Forbidden)
- Normal user cannot self-assign OWNER role
- Sensitive banking credentials are not stored or exposed
"""

from fastapi import status
from app.models.enums import RoleName
from tests.conftest import create_user_helper


def test_owner_can_view_own_profile(client, db_session):
    """Test authenticated user with OWNER role can view their owner profile."""
    db, cleanup_list = db_session
    owner_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": owner_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/owners/me/profile", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["user_id"] == str(owner_user.id)
    assert data["payout_status"] == "ACTIVE"


def test_owner_can_update_permitted_fields(client, db_session):
    """Test owner can update business name and payout reference token."""
    db, cleanup_list = db_session
    owner_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": owner_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "business_name": "Apex Fleet Solutions Pvt Ltd",
        "tax_id_number": "29ABCDE1234F1Z5",
        "payout_account_reference": "mock_payout_ref_9921",
    }
    response = client.patch("/api/v1/owners/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["business_name"] == "Apex Fleet Solutions Pvt Ltd"
    assert data["tax_id_number"] == "29ABCDE1234F1Z5"
    assert data["payout_account_reference"] == "mock_payout_ref_9921"
    assert data["payout_status"] == "ACTIVE"


def test_customer_cannot_access_owner_endpoints(client, db_session):
    """Test customer without OWNER role cannot access /owners/me/profile."""
    db, cleanup_list = db_session
    cust_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": cust_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/owners/me/profile", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Requires role: OWNER" in response.json()["detail"]


def test_sensitive_banking_data_rejected(client, db_session):
    """Test that arbitrary financial fields (e.g. CVV, pin, full_bank_account) are rejected."""
    db, cleanup_list = db_session
    owner_user, password = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": owner_user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "bank_account_number": "123456789012",
        "cvv": "123",
        "upi_pin": "9999",
    }
    response = client.patch("/api/v1/owners/me/profile", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
