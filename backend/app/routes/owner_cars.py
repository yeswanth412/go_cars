"""Owner Car Fleet Routes.

Endpoints for vehicle fleet owners:
- Car registration & CRUD (/owners/me/cars*)
- Image gallery management (/owners/me/cars/{car_id}/images*)
- Compliance document submission (/owners/me/cars/{car_id}/documents*)
- Blackout schedule management (/owners/me/cars/{car_id}/blackout-periods*)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.car import (
    CarCreateRequest,
    CarUpdateRequest,
    CarDetailResponse,
    PaginatedCarDetailResponse,
)
from app.schemas.car_image import CarImageCreateRequest, CarImageResponse
from app.schemas.car_document import CarDocumentCreateRequest, CarDocumentResponse
from app.schemas.blackout_period import BlackoutPeriodCreateRequest, BlackoutPeriodResponse
from app.services.car_service import CarService
from app.services.car_image_service import CarImageService
from app.services.car_document_service import CarDocumentService
from app.services.blackout_period_service import BlackoutPeriodService

router = APIRouter(prefix="/owners/me/cars", tags=["Owner Cars"])


# =============================================================================
# Car CRUD
# =============================================================================

@router.post(
    "",
    response_model=CarDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Car (Owner)",
    description="Register a new vehicle with initial status PENDING_APPROVAL. Requires OWNER role.",
)
def create_car(
    request: CarCreateRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Register a new vehicle linked to current owner."""
    car_service = CarService(db)
    return car_service.create_car(current_owner.id, request)


@router.get(
    "",
    response_model=PaginatedCarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="List My Cars (Owner)",
    description="Retrieve paginated list of cars owned by the authenticated user. Requires OWNER role.",
)
def list_my_cars(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING_APPROVAL, AVAILABLE)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> PaginatedCarDetailResponse:
    """List owned vehicles."""
    car_service = CarService(db)
    return car_service.list_owner_cars(current_owner.id, status_filter, page, page_size)


@router.get(
    "/{car_id}",
    response_model=CarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get My Car Details (Owner)",
    description="Retrieve full details of an owned car including images, documents, and blackout periods. Requires OWNER role.",
)
def get_my_car(
    car_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Get vehicle details for an owned car."""
    car_service = CarService(db)
    return car_service.get_owner_car(car_id, current_owner.id)


@router.patch(
    "/{car_id}",
    response_model=CarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update My Car (Owner)",
    description="Update mutable operational attributes. Rates, status, and registration cannot be modified. Requires OWNER role.",
)
def update_my_car(
    car_id: UUID,
    request: CarUpdateRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Partially update an owned vehicle."""
    car_service = CarService(db)
    return car_service.update_owner_car(car_id, current_owner.id, request)


@router.delete(
    "/{car_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete or Archive Car (Owner)",
    description="Deletes car if no bookings exist; archives to INACTIVE if historical bookings exist. Requires OWNER role.",
)
def delete_my_car(
    car_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
):
    """Safely archive or delete an owned vehicle."""
    car_service = CarService(db)
    return car_service.delete_owner_car(car_id, current_owner.id)


# =============================================================================
# Car Images
# =============================================================================

@router.post(
    "/{car_id}/images",
    response_model=CarImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Car Image (Owner)",
    description="Add an image reference to an owned vehicle. Requires OWNER role.",
)
def add_car_image(
    car_id: UUID,
    request: CarImageCreateRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> CarImageResponse:
    """Upload/add vehicle image."""
    image_service = CarImageService(db)
    return image_service.add_image(car_id, current_owner.id, request)


@router.get(
    "/{car_id}/images",
    response_model=List[CarImageResponse],
    status_code=status.HTTP_200_OK,
    summary="List Car Images (Owner)",
    description="List all images for an owned vehicle. Requires OWNER role.",
)
def list_car_images(
    car_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> List[CarImageResponse]:
    """List vehicle images."""
    image_service = CarImageService(db)
    return image_service.list_images(car_id, current_owner.id)


@router.delete(
    "/{car_id}/images/{image_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Car Image (Owner)",
    description="Delete an image from an owned vehicle. Requires OWNER role.",
)
def delete_car_image(
    car_id: UUID,
    image_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
):
    """Delete a vehicle image."""
    image_service = CarImageService(db)
    image_service.delete_image(image_id, current_owner.id)
    return {"message": "Image deleted successfully"}


# =============================================================================
# Car Documents
# =============================================================================

@router.post(
    "/{car_id}/documents",
    response_model=CarDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Compliance Document (Owner)",
    description="Submit vehicle document for verification. Status defaults to PENDING. Requires OWNER role.",
)
def submit_car_document(
    car_id: UUID,
    request: CarDocumentCreateRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> CarDocumentResponse:
    """Submit vehicle document for review."""
    doc_service = CarDocumentService(db)
    return doc_service.submit_document(car_id, current_owner.id, request)


@router.get(
    "/{car_id}/documents",
    response_model=List[CarDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Car Documents (Owner)",
    description="List all compliance documents and review statuses for an owned vehicle. Requires OWNER role.",
)
def list_car_documents(
    car_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> List[CarDocumentResponse]:
    """List vehicle compliance documents."""
    doc_service = CarDocumentService(db)
    return doc_service.list_documents(car_id, current_owner.id)


# =============================================================================
# Blackout Periods
# =============================================================================

@router.post(
    "/{car_id}/blackout-periods",
    response_model=BlackoutPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Blackout Period (Owner)",
    description="Schedule an unavailability window. Validates non-overlapping UTC time window. Requires OWNER role.",
)
def create_blackout_period(
    car_id: UUID,
    request: BlackoutPeriodCreateRequest,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> BlackoutPeriodResponse:
    """Schedule vehicle blackout interval."""
    blackout_service = BlackoutPeriodService(db)
    return blackout_service.create_blackout(car_id, current_owner.id, request)


@router.get(
    "/{car_id}/blackout-periods",
    response_model=List[BlackoutPeriodResponse],
    status_code=status.HTTP_200_OK,
    summary="List Blackout Periods (Owner)",
    description="List all scheduled unavailability windows for an owned vehicle. Requires OWNER role.",
)
def list_blackout_periods(
    car_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
) -> List[BlackoutPeriodResponse]:
    """List scheduled blackout periods."""
    blackout_service = BlackoutPeriodService(db)
    return blackout_service.list_blackouts(car_id, current_owner.id)


@router.delete(
    "/{car_id}/blackout-periods/{blackout_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Blackout Period (Owner)",
    description="Remove a scheduled blackout window. Requires OWNER role.",
)
def delete_blackout_period(
    car_id: UUID,
    blackout_id: UUID,
    current_owner: User = Depends(require_roles(RoleName.OWNER.value)),
    db: Session = Depends(get_db),
):
    """Remove a blackout interval."""
    blackout_service = BlackoutPeriodService(db)
    blackout_service.delete_blackout(blackout_id, current_owner.id)
    return {"message": "Blackout period deleted successfully"}
