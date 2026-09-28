"""Security and Authentication test suite covering registration, login, JWT, and RBAC."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User, UserRole


def _email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}@example.com"


def _phone() -> str:
    return f"+9198{uuid.uuid4().int % 100000000:08d}"


# ==============================================================================
# 1-5: Registration & Password Hashing Tests
# ==============================================================================

def test_successful_patient_registration(test_client, db_session):
    """1. Verify successful patient registration creates account and returns safe user profile."""
    email = _email("ananya")
    phone = _phone()
    payload = {
        "name": "Ananya Sen",
        "email": email,
        "phone": phone,
        "password": "SecurePassword123!",
    }
    response = test_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Ananya Sen"
    assert data["email"] == email
    assert data["phone"] == phone
    assert data["role"] == "patient"
    assert "id" in data
    # 5. Password hash is never returned
    assert "password_hash" not in data
    assert "password" not in data


def test_duplicate_email_rejection(test_client, db_session):
    """2. Verify duplicate email is rejected with 400 Bad Request."""
    dup_email = _email("duplicate")
    payload1 = {
        "name": "First User",
        "email": dup_email,
        "phone": _phone(),
        "password": "Password123",
    }
    response1 = test_client.post("/api/v1/auth/register", json=payload1)
    assert response1.status_code == 201

    payload2 = {
        "name": "Second User",
        "email": dup_email,
        "phone": _phone(),
        "password": "Password456",
    }
    response2 = test_client.post("/api/v1/auth/register", json=payload2)
    assert response2.status_code == 400
    assert "email" in response2.json()["detail"].lower()


def test_duplicate_phone_rejection(test_client, db_session):
    """3. Verify duplicate phone is rejected with 400 Bad Request."""
    dup_phone = _phone()
    payload1 = {
        "name": "User Phone 1",
        "email": _email("phone1"),
        "phone": dup_phone,
        "password": "Password123",
    }
    response1 = test_client.post("/api/v1/auth/register", json=payload1)
    assert response1.status_code == 201

    payload2 = {
        "name": "User Phone 2",
        "email": _email("phone2"),
        "phone": dup_phone,
        "password": "Password456",
    }
    response2 = test_client.post("/api/v1/auth/register", json=payload2)
    assert response2.status_code == 400
    assert "phone" in response2.json()["detail"].lower()


def test_password_is_hashed_in_database(test_client, db_session):
    """4. Verify password is never stored in plaintext and is hashed with bcrypt."""
    raw_password = "PlaintextPasswordToCheck999!"
    email = _email("hashcheck")
    payload = {
        "name": "Hash Verification User",
        "email": email,
        "password": raw_password,
    }
    response = test_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    user_in_db = db_session.query(User).filter(User.email == email).first()
    assert user_in_db is not None
    assert user_in_db.password_hash != raw_password
    assert user_in_db.password_hash.startswith("$2b$") or user_in_db.password_hash.startswith("$2a$")
    assert verify_password(raw_password, user_in_db.password_hash) is True


def test_password_hash_never_returned_in_login_or_me(test_client, db_session):
    """5. Verify password_hash is never exposed in login response or /me profile."""
    email = _email("noexposure")
    # Register
    reg_payload = {
        "name": "Exposure Test User",
        "email": email,
        "password": "ExposureTestPassword123",
    }
    reg_res = test_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # Login
    login_res = test_client.post("/api/v1/auth/login", json={
        "identifier": email,
        "password": "ExposureTestPassword123",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "password_hash" not in login_data
    assert "password_hash" not in login_data["user"]
    assert "password" not in login_data["user"]

    # /me
    token = login_data["access_token"]
    me_res = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert "password_hash" not in me_data
    assert "password" not in me_data


# ==============================================================================
# 6-8: Login Tests
# ==============================================================================

def test_successful_login_with_email_and_phone(test_client, db_session):
    """6. Verify successful login using either registered email or phone."""
    email = _email("dual")
    phone = _phone()
    reg_payload = {
        "name": "Dual Login User",
        "email": email,
        "phone": phone,
        "password": "DualPassword123!",
    }
    test_client.post("/api/v1/auth/register", json=reg_payload)

    # Login with email
    res_email = test_client.post("/api/v1/auth/login", json={
        "identifier": email,
        "password": "DualPassword123!",
    })
    assert res_email.status_code == 200
    assert "access_token" in res_email.json()
    assert res_email.json()["token_type"] == "bearer"
    assert res_email.json()["user"]["email"] == email

    # Login with phone
    res_phone = test_client.post("/api/v1/auth/login", json={
        "identifier": phone,
        "password": "DualPassword123!",
    })
    assert res_phone.status_code == 200
    assert "access_token" in res_phone.json()
    assert res_phone.json()["user"]["phone"] == phone


def test_invalid_password_rejected(test_client, db_session):
    """7. Verify invalid password yields HTTP 401 Unauthorized."""
    email = _email("failpass")
    reg_payload = {
        "name": "Auth Fail User",
        "email": email,
        "password": "CorrectPassword123",
    }
    test_client.post("/api/v1/auth/register", json=reg_payload)

    response = test_client.post("/api/v1/auth/login", json={
        "identifier": email,
        "password": "WrongPassword!",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_invalid_credentials_rejected_nonexistent(test_client, db_session):
    """8. Verify non-existent email/phone yields generic HTTP 401 Unauthorized."""
    response = test_client.post("/api/v1/auth/login", json={
        "identifier": "doesnotexist@example.com",
        "password": "SomePassword",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ==============================================================================
# 9-12: JWT Validation Tests
# ==============================================================================

def test_valid_jwt_accepted(test_client, db_session):
    """9. Verify valid JWT is accepted at protected endpoint."""
    user = User(
        name="Valid Token User",
        email=_email("validjwt"),
        password_hash=hash_password("password"),
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    response = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


def test_missing_jwt_rejected(test_client):
    """10. Verify request with missing Authorization header yields HTTP 401."""
    response = test_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_invalid_jwt_rejected(test_client):
    """11. Verify fabricated or malformed JWT yields HTTP 401."""
    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer completely.fake.token.here"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_expired_jwt_rejected(test_client, db_session):
    """12. Verify expired JWT yields HTTP 401 with expiration detail."""
    user = User(
        name="Expired User",
        email=_email("expired"),
        password_hash=hash_password("password"),
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    # Generate token already expired 10 minutes ago
    expired_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        expires_delta=timedelta(minutes=-10),
    )
    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


# ==============================================================================
# 13-17: Role-Based Access Control (RBAC) Tests
# ==============================================================================

def test_patient_role_accepted_by_patient_dependency(test_client, db_session):
    """13. Verify Patient role is accepted by require_patient endpoint."""
    user = User(
        name="Patient Alice",
        email=_email("alice_pat"),
        password_hash=hash_password("pw"),
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    res = test_client.get(
        "/api/v1/auth/test/patient-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "patient"


def test_patient_rejected_from_staff_only_dependency(test_client, db_session):
    """14. Verify Patient role is rejected with HTTP 403 from require_staff endpoint."""
    user = User(
        name="Patient Bob",
        email=_email("bob_pat"),
        password_hash=hash_password("pw"),
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    res = test_client.get(
        "/api/v1/auth/test/staff-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_patient_rejected_from_admin_only_dependency(test_client, db_session):
    """15. Verify Patient role is rejected with HTTP 403 from require_admin endpoint."""
    user = User(
        name="Patient Charlie",
        email=_email("charlie_pat"),
        password_hash=hash_password("pw"),
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    res = test_client.get(
        "/api/v1/auth/test/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_staff_accepted_by_staff_dependency(test_client, db_session):
    """16. Verify Staff role is accepted by require_staff dependency."""
    user = User(
        name="Staff Member Divya",
        email=_email("divya_staff"),
        password_hash=hash_password("pw"),
        role=UserRole.STAFF,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    res = test_client.get(
        "/api/v1/auth/test/staff-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "staff"


def test_admin_accepted_by_admin_dependency(test_client, db_session):
    """17. Verify Admin role is accepted by require_admin dependency."""
    user = User(
        name="Admin Boss",
        email=_email("admin_boss"),
        password_hash=hash_password("pw"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    res = test_client.get(
        "/api/v1/auth/test/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


# ==============================================================================
# 18-20: Role Escalation Prevention Tests
# ==============================================================================

def test_user_cannot_modify_own_role_through_public_api(test_client, db_session):
    """18. Verify that public registration ignores requested role or keeps role as PATIENT."""
    email = _email("hacker1")
    payload = {
        "name": "Hacker WannaBeAdmin",
        "email": email,
        "password": "Password123!",
        "role": "admin",
    }
    response = test_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "patient"  # Role was NOT set to admin

    # Check DB record
    user_in_db = db_session.query(User).filter(User.email == email).first()
    assert user_in_db.role == UserRole.PATIENT


def test_public_registration_cannot_create_admin(test_client, db_session):
    """19. Verify public registration strictly prevents admin account creation."""
    email = _email("fakeadmin")
    payload = {
        "name": "Fake Admin",
        "email": email,
        "password": "Password123!",
        "role": "admin",
    }
    response = test_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "patient"


def test_public_registration_cannot_create_staff(test_client, db_session):
    """20. Verify public registration strictly prevents staff account creation."""
    email = _email("fakestaff")
    payload = {
        "name": "Fake Staff",
        "email": email,
        "password": "Password123!",
        "role": "staff",
    }
    response = test_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "patient"


# ==============================================================================
# 21: Logout Endpoint Test
# ==============================================================================

def test_logout_endpoint(test_client):
    """21. Verify logout endpoint provides clean client/session termination response."""
    response = test_client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "discard" in response.json()["message"].lower()
