"""Tests for Car Document Compliance & Verification (Phase 5)."""

import uuid
import pytest
from fastapi import status
from app.models.enums import RoleName, DocumentType, DocumentVerificationStatus
from tests.conftest import create_user_helper


def create_car_payload():
    suffix = str(uuid.uuid4())[:6].upper()
    return {
        "brand": "Maruti",
        "model": "Swift",
        "year": 2022,
        "registration_number": f"KA04DOC{suffix}",
        "fuel_type": "PETROL",
        "transmission": "MANUAL",
        "seating_capacity": 5,
        "odometer_km": 15000,
        "rc_number": f"RC-DOC-{suffix}",
        "insurance_policy_number": f"INS-DOC-{suffix}",
        "insurance_expiry_date": "2027-10-15",
        "city": "Bangalore",
        "address": "Koramangala 4th Block",
        "hourly_rate": "120.00",
        "daily_rate": "1800.00",
        "weekly_rate": "11000.00",
        "is_self_drive_allowed": True,
        "is_driver_allowed": True,
    }


def test_car_document_submission_and_admin_verification(client, db_session):
    """Test owner submitting compliance docs and admin verification/rejection."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}

    login_a = client.post("/api/v1/auth/login", json={"email": admin.email, "password": pass_a})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # 1. Owner creates car
    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers_o)
    car_id = car_res.json()["id"]

    # 2. Owner submits RC document
    rc_payload = {
        "document_type": DocumentType.RC_BOOK.value,
        "document_url": "https://storage.gocars.com/docs/rc_swift.pdf",
        "expiry_date": "2032-01-01",
    }
    doc_res = client.post(f"/api/v1/owners/me/cars/{car_id}/documents", json=rc_payload, headers=headers_o)
    assert doc_res.status_code == status.HTTP_201_CREATED
    doc_data = doc_res.json()
    assert doc_data["document_type"] == DocumentType.RC_BOOK.value
    assert doc_data["verification_status"] == DocumentVerificationStatus.PENDING.value
    doc_id = doc_data["id"]

    # 3. Owner submits Insurance document
    ins_payload = {
        "document_type": DocumentType.INSURANCE.value,
        "document_url": "https://storage.gocars.com/docs/ins_swift.pdf",
        "expiry_date": "2027-10-15",
    }
    ins_res = client.post(f"/api/v1/owners/me/cars/{car_id}/documents", json=ins_payload, headers=headers_o)
    assert ins_res.status_code == status.HTTP_201_CREATED
    ins_id = ins_res.json()["id"]

    # 4. Owner lists documents
    list_res = client.get(f"/api/v1/owners/me/cars/{car_id}/documents", headers=headers_o)
    assert list_res.status_code == status.HTTP_200_OK
    assert len(list_res.json()) == 2

    # 5. Non-admin attempts verification -> 403
    verify_payload = {
        "verification_status": DocumentVerificationStatus.VERIFIED.value,
    }
    forbidden_res = client.patch(
        f"/api/v1/admin/car-documents/{doc_id}/verification",
        json=verify_payload,
        headers=headers_o,
    )
    assert forbidden_res.status_code == status.HTTP_403_FORBIDDEN

    # 6. Admin approves RC document
    admin_verify_res = client.patch(
        f"/api/v1/admin/car-documents/{doc_id}/verification",
        json=verify_payload,
        headers=headers_a,
    )
    assert admin_verify_res.status_code == status.HTTP_200_OK
    assert admin_verify_res.json()["verification_status"] == DocumentVerificationStatus.VERIFIED.value

    # 7. Admin rejects Insurance document with reason
    reject_payload = {
        "verification_status": DocumentVerificationStatus.REJECTED.value,
        "rejection_reason": "Policy copy is illegible. Please re-upload.",
    }
    admin_reject_res = client.patch(
        f"/api/v1/admin/car-documents/{ins_id}/verification",
        json=reject_payload,
        headers=headers_a,
    )
    assert admin_reject_res.status_code == status.HTTP_200_OK
    assert admin_reject_res.json()["verification_status"] == DocumentVerificationStatus.REJECTED.value
    assert admin_reject_res.json()["rejection_reason"] == "Policy copy is illegible. Please re-upload."


def test_reupload_document_resets_verification_status(client, db_session):
    """Test re-submitting an existing document type resets status to PENDING."""
    db, cleanup_list = db_session
    owner, pass_o = create_user_helper(db, cleanup_list, role_names=[RoleName.OWNER.value])
    admin, pass_a = create_user_helper(db, cleanup_list, role_names=[RoleName.ADMIN.value])

    login_o = client.post("/api/v1/auth/login", json={"email": owner.email, "password": pass_o})
    headers_o = {"Authorization": f"Bearer {login_o.json()['access_token']}"}
    login_a = client.post("/api/v1/auth/login", json={"email": admin.email, "password": pass_a})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    car_res = client.post("/api/v1/owners/me/cars", json=create_car_payload(), headers=headers_o)
    car_id = car_res.json()["id"]

    # Initial submission
    doc_res = client.post(
        f"/api/v1/owners/me/cars/{car_id}/documents",
        json={
            "document_type": DocumentType.POLLUTION_CERTIFICATE.value,
            "document_url": "https://storage.gocars.com/puc.pdf",
            "expiry_date": "2026-12-31",
        },
        headers=headers_o,
    )
    doc_id = doc_res.json()["id"]

    # Admin approves
    client.patch(
        f"/api/v1/admin/car-documents/{doc_id}/verification",
        json={"verification_status": DocumentVerificationStatus.VERIFIED.value},
        headers=headers_a,
    )

    # Owner re-submits updated PUC -> status resets to PENDING
    reupload_res = client.post(
        f"/api/v1/owners/me/cars/{car_id}/documents",
        json={
            "document_type": DocumentType.POLLUTION_CERTIFICATE.value,
            "document_url": "https://storage.gocars.com/puc_v2.pdf",
            "expiry_date": "2027-12-31",
        },
        headers=headers_o,
    )
    assert reupload_res.status_code == status.HTTP_201_CREATED
    assert reupload_res.json()["verification_status"] == DocumentVerificationStatus.PENDING.value
