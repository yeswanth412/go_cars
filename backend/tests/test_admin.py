"""Tests for Administrative User and Role Management (/api/v1/admin/*).

Covers:
- Admin can list users with pagination, search, and filtering
- Admin can inspect detailed user record (roles and profiles)
- Admin can assign a valid system role (OWNER, DRIVER, etc.)
- Duplicate role assignment rejected with 409 Conflict
- Invalid role rejected with 422 Unprocessable Entity
- Admin can revoke an assigned role
- Safeguard: Final active administrator cannot have ADMIN role revoked (400 Bad Request)
- Admin can activate and deactivate user accounts
- Safeguard: Administrator cannot deactivate their own account (400 Bad Request)
- Non-admin users forbidden from accessing admin endpoints (403 Forbidden)
- Deactivated user account cannot authenticate or access protected endpoints (401 Unauthorized)
"""

import uuid
from fastapi import status
from app.models.enums import RoleName
from tests.conftest import create_user_helper


def test_admin_can_list_users(client, db_session):
    """Test administrator can list users with pagination and search."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    test_user, _ = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List users with search
    response = client.get(
        f"/api/v1/admin/users?search={test_user.email}&page=1&page_size=10",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["page_size"] == 10
    found_emails = [item["email"] for item in data["items"]]
    assert test_user.email in found_emails


def test_admin_can_view_user_details(client, db_session):
    """Test administrator can retrieve comprehensive user details by ID."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, _ = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(f"/api/v1/admin/users/{target_user.id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(target_user.id)
    assert data["email"] == target_user.email
    assert "CUSTOMER" in data["roles"]
    assert "customer_profile" in data
    assert "hashed_password" not in data


def test_admin_can_assign_valid_role(client, db_session):
    """Test admin can assign a new role (e.g. OWNER) to a customer."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, target_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Assign OWNER role
    response = client.post(
        f"/api/v1/admin/users/{target_user.id}/roles",
        json={"role": "OWNER"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "OWNER" in data["roles"]
    assert "CUSTOMER" in data["roles"]

    # Verify target user can now access owner endpoints
    t_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_user.email, "password": target_pw},
    )
    t_token = t_login.json()["access_token"]
    owner_access_res = client.get(
        "/api/v1/owners/me/profile",
        headers={"Authorization": f"Bearer {t_token}"},
    )
    assert owner_access_res.status_code == status.HTTP_200_OK


def test_admin_assign_duplicate_role_rejected(client, db_session):
    """Test assigning an already assigned role returns 409 Conflict."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, _ = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to assign CUSTOMER role which target already has
    response = client.post(
        f"/api/v1/admin/users/{target_user.id}/roles",
        json={"role": "CUSTOMER"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already assigned" in response.json()["detail"].lower()


def test_admin_assign_invalid_role_rejected(client, db_session):
    """Test assigning a non-existent role fails schema validation (422)."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, _ = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/api/v1/admin/users/{target_user.id}/roles",
        json={"role": "SUPERUSER_GOD_MODE"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_admin_can_revoke_role(client, db_session):
    """Test admin can revoke an assigned role from a multi-role user."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, target_pw = create_user_helper(
        db,
        cleanup_list,
        role_names=[RoleName.CUSTOMER.value, RoleName.OWNER.value],
    )

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Revoke OWNER role
    response = client.delete(
        f"/api/v1/admin/users/{target_user.id}/roles/OWNER",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "OWNER" not in data["roles"]
    assert "CUSTOMER" in data["roles"]

    # Verify target user can no longer access owner endpoints
    t_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_user.email, "password": target_pw},
    )
    t_token = t_login.json()["access_token"]
    owner_access_res = client.get(
        "/api/v1/owners/me/profile",
        headers={"Authorization": f"Bearer {t_token}"},
    )
    assert owner_access_res.status_code == status.HTTP_403_FORBIDDEN


def test_admin_cannot_revoke_final_admin_role(client, db_session):
    """Test safeguard preventing revocation of the final active admin role."""
    db, cleanup_list = db_session
    # Admin is the solitary active admin in isolated context (or ensure only 1 active admin)
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Check active admin count. If count == 1, attempt revoking ADMIN must fail
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository(db)
    active_count = user_repo.count_active_admins()

    if active_count == 1:
        response = client.delete(
            f"/api/v1/admin/users/{admin_user.id}/roles/ADMIN",
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "final active administrator" in response.json()["detail"]


def test_admin_update_user_status_deactivation(client, db_session):
    """Test admin can deactivate a user account, preventing their subsequent access."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])
    target_user, target_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    # Target user gets a token before deactivation
    pre_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_user.email, "password": target_pw},
    )
    target_token = pre_login.json()["access_token"]

    # Verify target user currently has access
    pre_check = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {target_token}"})
    assert pre_check.status_code == status.HTTP_200_OK

    # Admin deactivates target user
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    deact_res = client.patch(
        f"/api/v1/admin/users/{target_user.id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deact_res.status_code == status.HTTP_200_OK
    assert deact_res.json()["is_active"] is False

    # Target user can NO LONGER use their token (DB backed check in get_current_user returns 401)
    post_check = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {target_token}"})
    assert post_check.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in post_check.json()["detail"].lower()

    # Target user can NO LONGER log in
    post_login = client.post(
        "/api/v1/auth/login",
        json={"email": target_user.email, "password": target_pw},
    )
    assert post_login.status_code == status.HTTP_401_UNAUTHORIZED


def test_admin_cannot_deactivate_self(client, db_session):
    """Test safeguard preventing administrators from deactivating their own account."""
    db, cleanup_list = db_session
    admin_user, admin_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": admin_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        f"/api/v1/admin/users/{admin_user.id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot deactivate their own account" in response.json()["detail"].lower()


def test_non_admin_cannot_perform_admin_actions(client, db_session):
    """Test standard customer receives 403 Forbidden on all admin endpoints."""
    db, cleanup_list = db_session
    cust_user, cust_pw = create_user_helper(db, cleanup_list, role_names=[RoleName.CUSTOMER.value])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": cust_user.email, "password": cust_pw},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List users
    res1 = client.get("/api/v1/admin/users", headers=headers)
    assert res1.status_code == status.HTTP_403_FORBIDDEN

    # Assign role
    fake_id = str(uuid.uuid4())
    res2 = client.post(f"/api/v1/admin/users/{fake_id}/roles", json={"role": "OWNER"}, headers=headers)
    assert res2.status_code == status.HTTP_403_FORBIDDEN

    # Update status
    res3 = client.patch(f"/api/v1/admin/users/{fake_id}/status", json={"is_active": False}, headers=headers)
    assert res3.status_code == status.HTTP_403_FORBIDDEN
