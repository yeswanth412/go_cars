"""Car Compliance Document Schemas.

Defines schemas for vehicle legal compliance documents and administrator verification workflows.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.enums import DocumentType, DocumentVerificationStatus


class CarDocumentCreateRequest(BaseModel):
    """Schema for owner submitting vehicle compliance documents."""

    document_type: DocumentType = Field(
        ...,
        description="Type of document (RC_BOOK, INSURANCE, POLLUTION_CERTIFICATE, FITNESS_CERTIFICATE)",
    )
    document_url: str = Field(
        ...,
        max_length=500,
        description="Secure document URL or storage reference",
    )
    expiry_date: Optional[date] = Field(
        None,
        description="Document validity expiry date if applicable",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("document_url")
    @classmethod
    def clean_url(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Document URL cannot be empty")
        return cleaned


class DocumentVerificationRequest(BaseModel):
    """Administrative verification decision payload."""

    verification_status: DocumentVerificationStatus = Field(
        ...,
        description="Decision status (VERIFIED or REJECTED)",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Reason for rejection (mandatory if verification_status is REJECTED)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "DocumentVerificationRequest":
        if self.verification_status == DocumentVerificationStatus.REJECTED:
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("Rejection reason is required when status is REJECTED")
        return self


class CarDocumentResponse(BaseModel):
    """Compliance document response representation."""

    id: UUID
    car_id: UUID
    document_type: DocumentType
    document_url: str
    verification_status: DocumentVerificationStatus
    rejection_reason: Optional[str] = None
    expiry_date: Optional[date] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
