"""Tests for General User Profile Management (/api/v1/users/me).

Covers:
- View own profile (safe fields, no password hash exposure)
- Partial update full name
- Partial update phone number
- Rejection of duplicate phone number (409 Conflict)
- Prevention of mass-assignment for protected attributes (roles, is_active, id)
- Unauthenticated requests (401 Missing/Invalid token)
"""

import uuid
from fastapi import status
from tests.conftest import create_user_helper


def test_get_own_profile_success(client, db_session):
    """Test authenticated user can retrieve their safe profile information."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list)

    # Login to get JWT
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch profile
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["full_name"] == user.full_name
    assert data["phone_number"] == user.phone_number
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert "CUSTOMER" in data["roles"]
    assert "hashed_password" not in data
    assert "password" not in data


def test_patch_own_profile_full_name(client, db_session):
    """Test user can partially update their full name."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list)

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {"full_name": "Updated John Doe"}
    response = client.patch("/api/v1/users/me", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["full_name"] == "Updated John Doe"
    assert data["phone_number"] == user.phone_number  # Unchanged


def test_patch_own_profile_phone_number(client, db_session):
    """Test user can partially update their phone number."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list)

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    new_phone = f"987{str(uuid.uuid4())[:7]}"
    update_payload = {"phone_number": new_phone}
    response = client.patch("/api/v1/users/me", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["phone_number"] == new_phone


def test_patch_own_profile_duplicate_phone_rejected(client, db_session):
    """Test that updating phone to an already registered number returns 409 Conflict."""
    db, cleanup_list = db_session
    user1, _ = create_user_helper(db, cleanup_list)
    user2, password2 = create_user_helper(db, cleanup_list)

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user2.email, "password": password2},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to take user1's phone number
    response = client.patch(
        "/api/v1/users/me",
        json={"phone_number": user1.phone_number},
        headers=headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already registered" in response.json()["detail"].lower()


def test_patch_protected_fields_mass_assignment_prevented(client, db_session):
    """Test that clients cannot inject protected fields (e.g. roles, is_active, is_verified)."""
    db, cleanup_list = db_session
    user, password = create_user_helper(db, cleanup_list)

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    malicious_payload = {
        "full_name": "Legit Name",
        "roles": ["ADMIN"],
        "is_active": False,
        "is_verified": True,
        "id": str(uuid.uuid4()),
    }
    response = client.patch("/api/v1/users/me", json=malicious_payload, headers=headers)
    # Extra forbidden attributes cause validation error (422)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_profile_missing_token_unauthorized(client):
    """Test unauthenticated request to /users/me returns 401."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "missing" in response.json()["detail"].lower()


def test_profile_invalid_token_unauthorized(client):
    """Test request with malformed/invalid token returns 401."""
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
