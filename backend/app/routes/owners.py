"""Owner Profile Routes.

Endpoints:
- GET   /owners/me/profile: View authenticated fleet owner's profile
- PATCH /owners/me/profile: Update owner profile details (business info, payout reference)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.owner import OwnerProfileResponse, OwnerProfileUpdateRequest
from app.services.owner_service import OwnerService

router = APIRouter(prefix="/owners", tags=["Owners"])


@router.get(
    "/me/profile",
    response_model=OwnerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Owner Profile",
    description="Retrieve the vehicle fleet owner profile for the authenticated user. Requires OWNER role.",
)
def get_owner_profile(
    current_user: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> OwnerProfileResponse:
    """Fetch owner profile information for the authenticated owner."""
    owner_service = OwnerService(db)
    return owner_service.get_profile(current_user.id)


@router.patch(
    "/me/profile",
    response_model=OwnerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Owner Profile",
    description="Update owner business details and payout account reference. Requires OWNER role.",
)
def update_owner_profile(
    request: OwnerProfileUpdateRequest,
    current_user: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> OwnerProfileResponse:
    """Update owner business information and payout reference."""
    owner_service = OwnerService(db)
    return owner_service.update_profile(current_user.id, request)
