"""Pytest fixtures for GoCars test suite."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.fixture(scope="session")
def client():
    """Provides a FastAPI TestClient for integration tests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Provides an isolated database session with automatic cascade cleanup for test entities."""
    db = SessionLocal()
    created_user_ids = []

    yield db, created_user_ids

    # Cleanup test users (cascades to user_roles, customer_profiles, owner_profiles, driver_profiles, cars, bookings)
    try:
        from app.models.booking import Booking
        from app.models.car import Car, CarImage, CarDocument, CarBlackoutPeriod

        for uid in created_user_ids:
            db.query(Booking).filter(
                (Booking.customer_id == uid) | (Booking.driver_id == uid)
            ).delete(synchronize_session=False)

            cars = db.query(Car).filter(Car.owner_id == uid).all()
            for car in cars:
                db.query(Booking).filter(Booking.car_id == car.id).delete(synchronize_session=False)
                db.query(CarImage).filter(CarImage.car_id == car.id).delete(synchronize_session=False)
                db.query(CarDocument).filter(CarDocument.car_id == car.id).delete(synchronize_session=False)
                db.query(CarBlackoutPeriod).filter(CarBlackoutPeriod.car_id == car.id).delete(synchronize_session=False)
                db.delete(car)
            db.commit()

            user = db.query(User).filter(User.id == uid).first()
            if user:
                db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def create_user_helper(
    db,
    cleanup_list,
    role_names=None,
    is_active=True,
    password="TestPassword123!",
):
    """Helper to create a test user with specified roles and track it for cleanup."""
    if role_names is None:
        role_names = [RoleName.CUSTOMER.value]

    user_repo = UserRepository(db)
    suffix = str(uuid.uuid4())[:8]
    user = user_repo.create_user(
        full_name=f"Test User {suffix}",
        email=f"test_{suffix}@example.com",
        phone_number=f"901{suffix[:7]}",
        hashed_password=hash_password(password),
        role_names=role_names,
    )
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    cleanup_list.append(user.id)
    return user, password
