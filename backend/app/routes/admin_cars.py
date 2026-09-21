"""Admin Car Fleet Management Routes.

Endpoints for platform administrators:
- Vehicle inspection & listing (/admin/cars*)
- Vehicle onboarding approval (/admin/cars/{car_id}/approval)
- Operational status modification (/admin/cars/{car_id}/status)
- Compliance document verification (/admin/car-documents/{document_id}/verification)
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.car import (
    CarApprovalRequest,
    CarStatusUpdateRequest,
    CarDetailResponse,
    PaginatedCarDetailResponse,
)
from app.schemas.car_document import DocumentVerificationRequest, CarDocumentResponse
from app.services.car_service import CarService
from app.services.car_document_service import CarDocumentService

router = APIRouter(tags=["Admin Cars"])


@router.get(
    "/admin/cars",
    response_model=PaginatedCarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Cars (Admin)",
    description="Administrative query listing all vehicles across all owners with filtering and pagination. Requires ADMIN role.",
)
def admin_list_cars(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. PENDING_APPROVAL, AVAILABLE)"),
    city: Optional[str] = Query(None, description="Filter by operating city"),
    brand: Optional[str] = Query(None, description="Filter by car brand"),
    owner_id: Optional[UUID] = Query(None, description="Filter by owner user ID"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> PaginatedCarDetailResponse:
    """List all cars platform-wide."""
    car_service = CarService(db)
    return car_service.admin_list_cars(
        status_filter=status_filter,
        city=city,
        brand=brand,
        owner_id=owner_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/admin/cars/{car_id}",
    response_model=CarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Car Full Details (Admin)",
    description="Inspect comprehensive vehicle record including owner, compliance documents, images, and blackouts. Requires ADMIN role.",
)
def admin_get_car(
    car_id: UUID,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Inspect full vehicle record."""
    car_service = CarService(db)
    return car_service.admin_get_car(car_id)


@router.patch(
    "/admin/cars/{car_id}/approval",
    response_model=CarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or Reject Car Onboarding (Admin)",
    description="Approve (AVAILABLE) or reject (REJECTED) vehicle onboarding. Requires ADMIN role.",
)
def admin_approve_car(
    car_id: UUID,
    request: CarApprovalRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Approve or reject a car."""
    car_service = CarService(db)
    return car_service.admin_approve_car(car_id, request)


@router.patch(
    "/admin/cars/{car_id}/status",
    response_model=CarDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Car Operational Status (Admin)",
    description="Update car status to AVAILABLE, MAINTENANCE, SUSPENDED, or INACTIVE. Requires ADMIN role.",
)
def admin_update_car_status(
    car_id: UUID,
    request: CarStatusUpdateRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> CarDetailResponse:
    """Update operational status of a car."""
    car_service = CarService(db)
    return car_service.admin_update_status(car_id, request)


@router.patch(
    "/admin/car-documents/{document_id}/verification",
    response_model=CarDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Car Document (Admin)",
    description="Verify (VERIFIED) or reject (REJECTED) vehicle compliance document with reasons. Requires ADMIN role.",
)
def admin_verify_car_document(
    document_id: UUID,
    request: DocumentVerificationRequest,
    current_admin: User = Depends(require_roles(RoleName.ADMIN.value)),
    db: Session = Depends(get_db),
) -> CarDocumentResponse:
    """Verify or reject vehicle compliance document."""
    doc_service = CarDocumentService(db)
    return doc_service.admin_verify_document(document_id, request)
