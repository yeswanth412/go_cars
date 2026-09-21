"""Comprehensive Test Suite for GoCars Authentication & Authorization.

Covers:
- Registration (success, duplicate email, duplicate phone, password hashing, role assignment)
- Login (valid credentials, wrong password, unknown email, inactive account)
- JWT Validation (valid, expired, malformed, missing token)
- Current User (/auth/me endpoint)
- Role-Based Access Control (RBAC: CUSTOMER, OWNER, ADMIN, and multi-role users)
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status
from jose import jwt
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, create_access_token
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.fixture
def db_session():
    """Provides an isolated database session with automatic cleanup for test entities."""
    db = SessionLocal()
    created_user_ids = []

    yield db, created_user_ids

    # Cleanup any users created during tests
    for uid in created_user_ids:
        user = db.query(User).filter(User.id == uid).first()
        if user:
            db.delete(user)
    db.commit()
    db.close()


def test_successful_registration(client, db_session):
    """Test standard customer registration with default CUSTOMER role."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"user_{unique_suffix}@example.com"
    phone = f"987{unique_suffix[:7]}"

    payload = {
        "full_name": "Test Customer",
        "email": email.upper(),  # Test email normalization
        "phone_number": phone,
        "password": "SecurePassword123!",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["message"] == "User registered successfully"
    user_data = data["user"]
    assert user_data["email"] == email.lower()
    assert user_data["full_name"] == "Test Customer"
    assert user_data["roles"] == [RoleName.CUSTOMER.value]
    assert user_data["is_active"] is True
    assert user_data["is_verified"] is False
    assert "password" not in user_data
    assert "hashed_password" not in user_data

    # Track for cleanup
    cleanup_list.append(uuid.UUID(user_data["id"]))

    # Verify password was hashed in database with Argon2
    db_user = db.query(User).filter(User.id == uuid.UUID(user_data["id"])).first()
    assert db_user is not None
    assert db_user.hashed_password != "SecurePassword123!"
    assert "$argon2" in db_user.hashed_password


def test_registration_duplicate_email(client, db_session):
    """Test that attempting to register an existing email returns 409 Conflict."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"dup_{unique_suffix}@example.com"
    phone1 = f"911{unique_suffix[:7]}"
    phone2 = f"922{unique_suffix[:7]}"

    # First registration
    payload1 = {
        "full_name": "User One",
        "email": email,
        "phone_number": phone1,
        "password": "Password123",
    }
    res1 = client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == status.HTTP_201_CREATED
    cleanup_list.append(uuid.UUID(res1.json()["user"]["id"]))

    # Second registration with duplicate email (different casing)
    payload2 = {
        "full_name": "User Two",
        "email": email.upper(),
        "phone_number": phone2,
        "password": "Password123",
    }
    res2 = client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "Email is already registered" in res2.json()["detail"]


def test_registration_duplicate_phone(client, db_session):
    """Test that attempting to register an existing phone number returns 409 Conflict."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email1 = f"phone1_{unique_suffix}@example.com"
    email2 = f"phone2_{unique_suffix}@example.com"
    phone = f"933{unique_suffix[:7]}"

    # First registration
    payload1 = {
        "full_name": "User One",
        "email": email1,
        "phone_number": phone,
        "password": "Password123",
    }
    res1 = client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == status.HTTP_201_CREATED
    cleanup_list.append(uuid.UUID(res1.json()["user"]["id"]))

    # Second registration with duplicate phone
    payload2 = {
        "full_name": "User Two",
        "email": email2,
        "phone_number": phone,
        "password": "Password123",
    }
    res2 = client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "Phone number is already registered" in res2.json()["detail"]


def test_login_success(client, db_session):
    """Test successful login with valid credentials issuing a JWT token."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"login_{unique_suffix}@example.com"
    phone = f"944{unique_suffix[:7]}"
    password = "MySecretPassword123"

    # Register
    reg_payload = {
        "full_name": "Login User",
        "email": email,
        "phone_number": phone,
        "password": password,
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    cleanup_list.append(uuid.UUID(reg_res.json()["user"]["id"]))

    # Login
    login_payload = {"email": email, "password": password}
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == email


def test_login_invalid_password(client, db_session):
    """Test that login with incorrect password returns generic 401 Unauthorized."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"wrongpw_{unique_suffix}@example.com"
    phone = f"955{unique_suffix[:7]}"

    reg_payload = {
        "full_name": "User WrongPw",
        "email": email,
        "phone_number": phone,
        "password": "CorrectPassword123",
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    cleanup_list.append(uuid.UUID(reg_res.json()["user"]["id"]))

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword999"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_email(client):
    """Test that login with an unregistered email returns generic 401 Unauthorized."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_user_98124@example.com", "password": "SomePassword123"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_inactive_user(client, db_session):
    """Test that an inactive user account cannot log in."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"inactive_{unique_suffix}@example.com"
    phone = f"966{unique_suffix[:7]}"
    password = "ActivePassword123"

    # Create inactive user directly in DB
    user_repo = UserRepository(db)
    user = user_repo.create_user(
        full_name="Inactive User",
        email=email,
        phone_number=phone,
        hashed_password=hash_password(password),
        role_names=[RoleName.CUSTOMER.value],
    )
    user.is_active = False
    db.commit()
    cleanup_list.append(user.id)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in response.json()["detail"].lower()


def test_get_current_user_profile(client, db_session):
    """Test GET /auth/me returns the profile of the authenticated user."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"me_{unique_suffix}@example.com"
    phone = f"977{unique_suffix[:7]}"
    password = "Password123"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Me User", "email": email, "phone_number": phone, "password": password},
    )
    cleanup_list.append(uuid.UUID(reg_res.json()["user"]["id"]))

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "Me User"
    assert RoleName.CUSTOMER.value in data["roles"]


def test_auth_missing_token(client):
    """Test accessing protected endpoint without Authorization header returns 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "missing" in response.json()["detail"].lower()


def test_auth_invalid_token(client):
    """Test accessing protected endpoint with invalid JWT returns 401."""
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_garbage_token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "credentials" in response.json()["detail"].lower()


def test_auth_expired_token(client, db_session):
    """Test that an expired JWT token returns 401 Unauthorized."""
    unique_user_id = str(uuid.uuid4())
    # Create expired token (expired 10 minutes ago)
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": unique_user_id,
        "exp": int((now - timedelta(minutes=10)).timestamp()),
        "iat": int((now - timedelta(minutes=20)).timestamp()),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.effective_jwt_secret_key,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "credentials" in response.json()["detail"].lower()


def test_role_authorization_customer_cannot_access_admin_or_owner(client, db_session):
    """Test that standard customer receives 403 Forbidden on admin and owner endpoints."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"cust_{unique_suffix}@example.com"
    phone = f"988{unique_suffix[:7]}"
    password = "Password123"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Cust Only", "email": email, "phone_number": phone, "password": password},
    )
    cleanup_list.append(uuid.UUID(reg_res.json()["user"]["id"]))

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt admin endpoint
    admin_res = client.get("/api/v1/auth/admin-test", headers=headers)
    assert admin_res.status_code == status.HTTP_403_FORBIDDEN
    assert "Requires role: ADMIN" in admin_res.json()["detail"]

    # Attempt owner endpoint
    owner_res = client.get("/api/v1/auth/owner-test", headers=headers)
    assert owner_res.status_code == status.HTTP_403_FORBIDDEN
    assert "Requires role: OWNER" in owner_res.json()["detail"]


def test_role_authorization_admin_access(client, db_session):
    """Test that a user with ADMIN role can access the admin-test endpoint."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"admin_{unique_suffix}@example.com"
    phone = f"999{unique_suffix[:7]}"
    password = "AdminPassword123"

    user_repo = UserRepository(db)
    user = user_repo.create_user(
        full_name="Admin User",
        email=email,
        phone_number=phone,
        hashed_password=hash_password(password),
        role_names=[RoleName.ADMIN.value],
    )
    db.commit()
    cleanup_list.append(user.id)

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]

    response = client.get("/api/v1/auth/admin-test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Admin authorization verified successfully"


def test_role_authorization_multi_role_user(client, db_session):
    """Test that a multi-role user (CUSTOMER + OWNER) can access both customer and owner endpoints."""
    db, cleanup_list = db_session
    unique_suffix = str(uuid.uuid4())[:8]
    email = f"multirole_{unique_suffix}@example.com"
    phone = f"900{unique_suffix[:7]}"
    password = "MultiPassword123"

    user_repo = UserRepository(db)
    user = user_repo.create_user(
        full_name="Multi Role User",
        email=email,
        phone_number=phone,
        hashed_password=hash_password(password),
        role_names=[RoleName.CUSTOMER.value, RoleName.OWNER.value],
    )
    db.commit()
    cleanup_list.append(user.id)

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Can access /me
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == status.HTTP_200_OK
    roles = me_res.json()["roles"]
    assert RoleName.CUSTOMER.value in roles
    assert RoleName.OWNER.value in roles

    # Can access /owner-test
    owner_res = client.get("/api/v1/auth/owner-test", headers=headers)
    assert owner_res.status_code == status.HTTP_200_OK
    assert owner_res.json()["message"] == "Owner authorization verified successfully"

    # CANNOT access /admin-test (does not have ADMIN role)
    admin_res = client.get("/api/v1/auth/admin-test", headers=headers)
    assert admin_res.status_code == status.HTTP_403_FORBIDDEN
