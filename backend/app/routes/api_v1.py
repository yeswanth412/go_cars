"""API v1 router aggregator.

Collects and mounts all modular sub-routers for API version 1.
"""

from fastapi import APIRouter
from app.routes import health, auth, users, customers, owners, drivers, admin

api_router = APIRouter()

# Register sub-routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(customers.router)
api_router.include_router(owners.router)
api_router.include_router(drivers.router)
api_router.include_router(admin.router)
