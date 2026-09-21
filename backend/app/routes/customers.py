"""Customer Profile Routes.

Endpoints:
- GET   /customers/me/profile: View authenticated customer's rental profile
- PATCH /customers/me/profile: Update customer profile attributes (license, emergency contacts)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.customer import CustomerProfileResponse, CustomerProfileUpdateRequest
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "/me/profile",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer Profile",
    description="Retrieve the customer rental profile for the authenticated user. Requires CUSTOMER role.",
)
def get_customer_profile(
    current_user: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    """Fetch customer profile data for the authenticated customer."""
    customer_service = CustomerService(db)
    return customer_service.get_profile(current_user.id)


@router.patch(
    "/me/profile",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Customer Profile",
    description="Update customer profile details. Self-verification is strictly disallowed. Requires CUSTOMER role.",
)
def update_customer_profile(
    request: CustomerProfileUpdateRequest,
    current_user: User = Depends(require_roles(RoleName.CUSTOMER.value)),
    db: Session = Depends(get_db),
) -> CustomerProfileResponse:
    """Update customer driving license and emergency contact attributes."""
    customer_service = CustomerService(db)
    return customer_service.update_profile(current_user.id, request)
