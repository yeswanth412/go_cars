"""API v1 router aggregator.

Collects and mounts all modular sub-routers for API version 1.
"""

from fastapi import APIRouter
from app.routes import (
    health,
    auth,
    users,
    customers,
    owners,
    drivers,
    admin,
    owner_cars,
    admin_cars,
    cars,
    bookings,
    owner_bookings,
    driver_trips,
    admin_bookings,
)

api_router = APIRouter()

# Register sub-routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(customers.router)
api_router.include_router(owners.router)
api_router.include_router(drivers.router)
api_router.include_router(admin.router)

# Phase 5: Car Fleet Management routers
api_router.include_router(owner_cars.router)
api_router.include_router(admin_cars.router)
api_router.include_router(cars.router)

# Phase 6: Booking Management routers
api_router.include_router(bookings.router)
api_router.include_router(owner_bookings.router)
api_router.include_router(driver_trips.router)
api_router.include_router(admin_bookings.router)
