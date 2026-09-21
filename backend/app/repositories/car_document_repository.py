"""Car Document Repository.

Handles database persistence and queries for vehicle compliance documents.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.enums import DocumentVerificationStatus
from app.models.car import CarDocument


class CarDocumentRepository:
    """Repository managing CarDocument database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        car_id: UUID,
        document_type: str,
        document_url: str,
        expiry_date: Optional[date] = None,
    ) -> CarDocument:
        """Create a new car compliance document record with PENDING verification status."""
        doc = CarDocument(
            car_id=car_id,
            document_type=document_type,
            document_url=document_url,
            expiry_date=expiry_date,
            verification_status=DocumentVerificationStatus.PENDING.value,
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def get_by_id(self, document_id: UUID) -> Optional[CarDocument]:
        """Fetch document by primary key ID."""
        stmt = select(CarDocument).where(CarDocument.id == document_id)
        return self.db.scalars(stmt).first()

    def list_by_car_id(self, car_id: UUID) -> List[CarDocument]:
        """List all compliance documents for a car."""
        stmt = (
            select(CarDocument)
            .where(CarDocument.car_id == car_id)
            .order_by(CarDocument.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def update_verification(
        self,
        document: CarDocument,
        status: str,
        rejection_reason: Optional[str] = None,
    ) -> CarDocument:
        """Update document verification status and rejection rationale."""
        document.verification_status = status
        document.rejection_reason = rejection_reason
        self.db.flush()
        return document
