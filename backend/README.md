# GoCars — Backend

**GoCars** is a car mobility and rental platform backend built with **Python 3.11+**, **FastAPI**, **Pydantic v2**, **SQLAlchemy 2.0**, and **PostgreSQL (hosted on Supabase)**.

---

## Architecture Overview

GoCars follows a **Clean Layered Architecture (Modular Monolith)** to maintain strict separation of concerns, high testability, and clear business logic isolation:

```
FastAPI Routes (HTTP & Validation)
       │
       ▼
Service Layer (Domain Logic, State Transitions & Safeguards)
       │
       ▼
Repository Layer (Data Access & Eager-Loaded Persistence)
       │
       ▼
SQLAlchemy 2.0 ORM & PostgreSQL (Supabase)
```

- **Routes (`app/routes/`)**: Responsible for HTTP protocol handling, parameter validation with Pydantic schemas, dependency injection (`get_current_user`, `require_roles`), and returning HTTP status codes.
- **Services (`app/services/`)**: Implements business logic (role assignments, profile validation, driver duty transition rules, admin safeguards).
- **Repositories (`app/repositories/`)**: Encapsulates database read/write queries and transactions.
- **Models (`app/models/`)**: SQLAlchemy declarative models mapping to physical PostgreSQL tables.
- **Schemas (`app/schemas/`)**: Pydantic models for incoming request validation and outgoing JSON responses.

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI application entrypoint, CORS & lifespan
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (.env loader)
│   │   ├── database.py          # SQLAlchemy engine, sessionmaker, get_db
│   │   └── security.py          # Argon2 password hashing & JWT token generation/decoding
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── enums.py             # RoleName, DriverDutyStatus, etc.
│   │   ├── user.py              # User, Role, UserRole, CustomerProfile, OwnerProfile, DriverProfile
│   │   ├── car.py               # Car & Document models
│   │   ├── booking.py           # Booking models
│   │   ├── payment.py           # Payment models
│   │   └── review.py            # Review models
│   ├── schemas/                 # Pydantic validation schemas
│   │   ├── auth.py              # RegisterRequest, LoginRequest, TokenResponse
│   │   ├── user.py              # UserProfileResponse, UserProfileUpdateRequest
│   │   ├── customer.py          # CustomerProfileResponse, CustomerProfileUpdateRequest
│   │   ├── owner.py             # OwnerProfileResponse, OwnerProfileUpdateRequest
│   │   ├── driver.py            # DriverProfileResponse, DriverProfileUpdateRequest
│   │   ├── admin.py             # RoleAssignRequest, UserStatusUpdateRequest, UserDetailResponse, PaginatedUserResponse
│   │   └── health.py            # Health check response schema
│   ├── routes/                  # API endpoints
│   │   ├── api_v1.py            # Version 1 router aggregator
│   │   ├── auth.py              # /api/v1/auth/register, /login, /me
│   │   ├── users.py             # /api/v1/users/me
│   │   ├── customers.py         # /api/v1/customers/me/profile
│   │   ├── owners.py            # /api/v1/owners/me/profile
│   │   ├── drivers.py           # /api/v1/drivers/me/profile
│   │   ├── admin.py             # /api/v1/admin/users, /roles, /status
│   │   └── health.py            # /api/v1/health endpoint
│   ├── services/                # Business logic services
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── customer_service.py
│   │   ├── owner_service.py
│   │   ├── driver_service.py
│   │   └── admin_service.py
│   └── repositories/            # Data access repository layer
│       ├── user_repository.py
│       ├── customer_repository.py
│       ├── owner_repository.py
│       └── driver_repository.py
├── alembic/                     # Database migration environment
│   ├── versions/
│   │   └── 27e092d7c8ce_create_mvp_tables.py
│   └── env.py
├── tests/                       # Automated test suite (47 tests passing)
│   ├── conftest.py              # Pytest fixtures & isolated DB session teardown
│   ├── test_health.py           # Health check test cases
│   ├── test_auth.py             # Authentication & RBAC test cases
│   ├── test_users.py            # General user profile test cases
│   ├── test_customers.py        # Customer rental profile test cases
│   ├── test_owners.py           # Fleet owner profile test cases
│   ├── test_drivers.py          # Driver profile & duty status test cases
│   └── test_admin.py            # Admin user & role management test cases
├── .env                         # Local environment variables (ignored by git)
├── .env.example                 # Environment variables template
├── .gitignore
├── alembic.ini                  # Alembic migration configuration
└── requirements.txt             # Project dependencies
```

---

## Quickstart Guide

### 1. Setup Virtual Environment

From the `backend/` directory:

```bash
# Create virtual environment using Python 3.11
python3.11 -m venv venv

# Activate virtual environment
# On macOS / Linux:
source venv/bin/activate
# On Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Ensure `DATABASE_URL` points to your PostgreSQL database (e.g. Supabase connection pooler or direct connection).

### 4. Run the Development Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server will start at `http://127.0.0.1:8000`.

### 5. Verify the API

- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**:
  ```bash
  curl http://127.0.0.1:8000/api/v1/health
  ```

---

## Phase 4: User Profile & Role Management

### Endpoints Overview

| Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/users/me` | Authenticated | View own user profile, active status, verification status, and assigned roles. |
| `PATCH` | `/api/v1/users/me` | Authenticated | Update full name and phone number. Duplicate phone numbers are rejected with `409 Conflict`. |
| `GET` | `/api/v1/customers/me/profile` | `CUSTOMER` | View customer profile (driving license, emergency contact). |
| `PATCH` | `/api/v1/customers/me/profile` | `CUSTOMER` | Update driving license and emergency contact. Self-verification is strictly prohibited. |
| `GET` | `/api/v1/owners/me/profile` | `OWNER` | View owner profile (business name, tax ID, non-sensitive payout reference). |
| `PATCH` | `/api/v1/owners/me/profile` | `OWNER` | Update business name, tax ID, or payout reference token. |
| `GET` | `/api/v1/drivers/me/profile` | `DRIVER` | View commercial driver profile (license, experience, verification, duty status). |
| `PATCH` | `/api/v1/drivers/me/profile` | `DRIVER` | Update experience, city, or duty status. Unverified drivers cannot go `ONLINE`. |
| `GET` | `/api/v1/admin/users` | `ADMIN` | List users with pagination (`page`, `page_size`), search (`search`), and status filter (`is_active`). |
| `GET` | `/api/v1/admin/users/{user_id}` | `ADMIN` | Inspect user details including roles, customer profile, owner profile, and driver profile. |
| `POST` | `/api/v1/admin/users/{user_id}/roles` | `ADMIN` | Assign role (`ADMIN`, `CUSTOMER`, `OWNER`, `DRIVER`). Duplicate assignments return `409 Conflict`. |
| `DELETE` | `/api/v1/admin/users/{user_id}/roles/{role_name}`| `ADMIN` | Revoke a role. Safeguard blocks revoking the `ADMIN` role from the final active administrator. |
| `PATCH` | `/api/v1/admin/users/{user_id}/status` | `ADMIN` | Activate or deactivate user accounts. Safeguard blocks administrator self-deactivation. |

### Security & Business Safeguards
1. **Zero Password Hash Exposure**: Password hashes and sensitive credentials are never returned in any response schema.
2. **Identity from JWT Context**: Self-service endpoints derive user identity exclusively from the validated JWT token (`get_current_user`), preventing ID manipulation attacks.
3. **Mass-Assignment Defense**: Pydantic models use `extra="forbid"` to strictly reject unexpected attributes (`is_active`, `is_verified`, `roles`).
4. **Driver Duty Rule**: Commercial drivers must be verified (`verification_status == "APPROVED"`) before transitioning duty status to `ONLINE` or `ON_TRIP`.
5. **Administrative Safeguards**:
   - The final active administrator cannot have the `ADMIN` role revoked.
   - Administrators cannot deactivate their own account.
6. **Deactivation Enforcement**: `get_current_user` queries the database on every authenticated request and immediately blocks deactivated accounts with `401 Unauthorized`.

---

## Running Automated Tests

Run the complete test suite using `pytest`:

```bash
pytest tests/ -v
```

**Results**: `47 passed` across 6 test modules in ~45s.

---

## Database Migration Status

- Current head: `27e092d7c8ce`
- Phase 4 reuses the existing Supabase PostgreSQL schema created in Phase 2.
- **No new Alembic migration was required**.

---

## Development Roadmap

- [x] **Phase 1: Project Setup** (FastAPI, Pydantic, SQLAlchemy 2.0, Alembic, Health Check, Tests)
- [x] **Phase 2: Database Design** (Entities, Relationships, Constraints, Migrations)
- [x] **Phase 3: Authentication & Multi-Role Authorization** (JWT, Password Hashing, RBAC)
- [x] **Phase 4: User & Profile Management** (Customers, Owners, Drivers, Admin RBAC)
- [ ] **Phase 5: Car Fleet Management** (Specifications, Availability, Pricing Rules)
- [ ] **Phase 6: Booking Engine** (Self-drive, Car-with-driver, Overlap Prevention)
- [ ] **Phase 7: Pricing & Payments** (Dynamic pricing service, mock payment workflows)
- [ ] **Phase 8: Cancellation & Refunds** (State checks, refund calculation)
- [ ] **Phase 9: Reviews & Ratings** (Verified trip reviews)
- [ ] **Phase 10: Operations** (Breakdown handling, damage reports, notifications)
- [ ] **Phase 11: Admin Module** (Platform oversight, verifications)
- [ ] **Phase 12: AI Integrations** (RAG support assistant, tool-calling car search)
