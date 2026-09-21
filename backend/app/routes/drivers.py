"""Driver Profile Routes.

Endpoints:
- GET   /drivers/me/profile: View authenticated driver's profile
- PATCH /drivers/me/profile: Update driver operational details (experience, city, duty status)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.driver import DriverProfileResponse, DriverProfileUpdateRequest
from app.services.driver_service import DriverService

router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.get(
    "/me/profile",
    response_model=DriverProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Driver Profile",
    description="Retrieve the commercial driver profile for the authenticated user. Requires DRIVER role.",
)
def get_driver_profile(
    current_user: User = Depends(require_roles(RoleName.DRIVER.value)),
    db: Session = Depends(get_db),
) -> DriverProfileResponse:
    """Fetch driver profile details for the authenticated commercial driver."""
    driver_service = DriverService(db)
    return driver_service.get_profile(current_user.id)


@router.patch(
    "/me/profile",
    response_model=DriverProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Driver Profile",
    description="Update driver operational attributes. Unverified drivers cannot go ONLINE. Requires DRIVER role.",
)
def update_driver_profile(
    request: DriverProfileUpdateRequest,
    current_user: User = Depends(require_roles(RoleName.DRIVER.value)),
    db: Session = Depends(get_db),
) -> DriverProfileResponse:
    """Update driver experience, operating city, or duty availability."""
    driver_service = DriverService(db)
    return driver_service.update_profile(current_user.id, request)
