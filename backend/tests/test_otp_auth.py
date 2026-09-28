"""Comprehensive test suite for patient self-registration and OTP authentication."""

import uuid
from datetime import datetime, timedelta, timezone
from app.models.user import User, UserRole
from app.models.otp_token import OTPToken
from app.core.security import hash_password
from tests.conftest import make_test_user


def test_otp_request_and_verify_registration(test_client, db_session):
    """Test OTP request followed by verification for a new patient registration."""
    recipient = f"+9198765{uuid.uuid4().hex[:5]}"

    # 1. Request OTP
    req_res = test_client.post(
        "/api/v1/auth/otp/request",
        json={"recipient": recipient, "channel": "SMS", "purpose": "REGISTRATION"},
    )
    assert req_res.status_code == 200
    req_data = req_res.json()
    assert req_data["success"] is True
    assert req_data["recipient"] == recipient
    assert "delivery_status" in req_data

    # 2. Retrieve generated token from DB
    token_record = (
        db_session.query(OTPToken)
        .filter(OTPToken.recipient == recipient)
        .order_by(OTPToken.created_at.desc())
        .first()
    )
    assert token_record is not None
    assert len(token_record.otp_code) == 6

    # 3. Verify OTP and register patient
    verify_res = test_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "recipient": recipient,
            "otp_code": token_record.otp_code,
            "name": "OTP Test Patient",
        },
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert "access_token" in verify_data
    assert verify_data["user"]["name"] == "OTP Test Patient"
    assert verify_data["user"]["role"] == "patient"

    # Verify token is marked verified in DB
    db_session.refresh(token_record)
    assert token_record.is_verified is True


def test_otp_verify_existing_user_login(test_client, db_session):
    """Test OTP verification logs in an existing patient without creating a duplicate."""
    phone = f"+9198765{uuid.uuid4().hex[:5]}"
    existing_user = User(
        name="Existing Patient",
        phone=phone,
        password_hash=hash_password("pw123"),
        role=UserRole.PATIENT,
    )
    db_session.add(existing_user)
    db_session.commit()

    # Request OTP
    test_client.post(
        "/api/v1/auth/otp/request",
        json={"recipient": phone, "channel": "SMS", "purpose": "LOGIN"},
    )

    token_record = (
        db_session.query(OTPToken)
        .filter(OTPToken.recipient == phone)
        .order_by(OTPToken.created_at.desc())
        .first()
    )

    # Verify OTP
    res = test_client.post(
        "/api/v1/auth/otp/verify",
        json={"recipient": phone, "otp_code": token_record.otp_code},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["id"] == str(existing_user.id)
    assert data["user"]["name"] == "Existing Patient"


def test_otp_invalid_code_rejected(test_client, db_session):
    """Test that an incorrect OTP code is rejected with HTTP 400."""
    recipient = f"+9198765{uuid.uuid4().hex[:5]}"
    test_client.post(
        "/api/v1/auth/otp/request",
        json={"recipient": recipient, "channel": "SMS"},
    )

    res = test_client.post(
        "/api/v1/auth/otp/verify",
        json={"recipient": recipient, "otp_code": "000000"},
    )
    assert res.status_code == 400
    assert "Invalid OTP code" in res.json()["detail"]


def test_otp_expired_code_rejected(test_client, db_session):
    """Test that an expired OTP token is rejected with HTTP 400."""
    recipient = f"+9198765{uuid.uuid4().hex[:5]}"
    test_client.post(
        "/api/v1/auth/otp/request",
        json={"recipient": recipient, "channel": "SMS"},
    )

    token_record = (
        db_session.query(OTPToken)
        .filter(OTPToken.recipient == recipient)
        .order_by(OTPToken.created_at.desc())
        .first()
    )
    # Simulate expiration (10 minutes ago)
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    res = test_client.post(
        "/api/v1/auth/otp/verify",
        json={"recipient": recipient, "otp_code": token_record.otp_code},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_public_registration_coerces_to_patient(test_client, db_session):
    """Test that public self-registration strictly provisions PATIENT role even if STAFF requested."""
    email = f"hack_{uuid.uuid4().hex[:6]}@test.com"
    res = test_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Malicious User",
            "email": email,
            "password": "password123",
            "role": "staff",  # Escalation attempt
        },
    )
    assert res.status_code == 201
    user_data = res.json()
    assert user_data["role"] == "patient"
