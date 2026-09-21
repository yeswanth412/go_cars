"""Car Document Service.

Handles compliance document submissions, ownership checks, and administrative verification.
"""

from typing import List
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.car_repository import CarRepository
from app.repositories.car_document_repository import CarDocumentRepository
from app.schemas.car_document import (
    CarDocumentCreateRequest,
    CarDocumentResponse,
    DocumentVerificationRequest,
)


class CarDocumentService:
    """Service managing vehicle legal compliance documentation."""

    def __init__(self, db: Session):
        self.db = db
        self.car_repo = CarRepository(db)
        self.doc_repo = CarDocumentRepository(db)

    def _verify_car_ownership(self, car_id: UUID, owner_id: UUID):
        """Ensure car exists and is owned by caller."""
        car = self.car_repo.get_by_id(car_id)
        if not car:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Car not found",
            )
        if car.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage documents for this vehicle",
            )
        return car

    def submit_document(
        self,
        car_id: UUID,
        owner_id: UUID,
        request: CarDocumentCreateRequest,
    ) -> CarDocumentResponse:
        """Owner submits compliance document for verification."""
        self._verify_car_ownership(car_id, owner_id)

        try:
            doc = self.doc_repo.create(
                car_id=car_id,
                document_type=request.document_type.value,
                document_url=request.document_url,
                expiry_date=request.expiry_date,
            )
            self.db.commit()
            self.db.refresh(doc)
        except Exception:
            self.db.rollback()
            raise

        return CarDocumentResponse.model_validate(doc)

    def list_documents(self, car_id: UUID, owner_id: UUID) -> List[CarDocumentResponse]:
        """List documents and verification statuses for an owned vehicle."""
        self._verify_car_ownership(car_id, owner_id)
        docs = self.doc_repo.list_by_car_id(car_id)
        return [CarDocumentResponse.model_validate(d) for d in docs]

    def admin_verify_document(
        self,
        document_id: UUID,
        request: DocumentVerificationRequest,
    ) -> CarDocumentResponse:
        """Administrator approves or rejects a vehicle compliance document."""
        doc = self.doc_repo.get_by_id(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        try:
            updated = self.doc_repo.update_verification(
                document=doc,
                status=request.verification_status.value,
                rejection_reason=request.rejection_reason,
            )
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise

        return CarDocumentResponse.model_validate(updated)
