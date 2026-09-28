"""Authentication endpoints for registration, login, logout, and current user profile."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_patient, require_staff, require_admin
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    LogoutResponse,
    OTPRequestPayload,
    OTPRequestResponse,
    OTPVerifyPayload,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Patient Account",
    description="Public self-registration. Strictly provisions PATIENT accounts only. Staff and Admin cannot be created publicly.",
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Registers a new patient and returns the safe user profile."""
    user = AuthService.register_patient(db, request)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates via email or phone with password. Returns a signed JWT bearer token.",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticates credentials and returns a JWT access token."""
    return AuthService.authenticate_user(db, request)


@router.post(
    "/otp/request",
    response_model=OTPRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Request OTP Code",
    description="Generates a 6-digit OTP code for patient passwordless login or registration.",
)
def request_otp(
    request: OTPRequestPayload,
    db: Session = Depends(get_db),
) -> OTPRequestResponse:
    """Generates an OTP code and dispatches it via configured provider."""
    return AuthService.request_otp(db, request)


@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP Code and Login/Register",
    description="Verifies an OTP code and logs in or registers the patient account.",
)
def verify_otp(
    request: OTPVerifyPayload,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verifies OTP and returns a JWT access token."""
    return AuthService.verify_otp(db, request)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Client session termination. Since JWT bearer tokens are stateless, client must discard the token.",
)
def logout() -> LogoutResponse:
    """Stateless logout confirmation."""
    return LogoutResponse(
        success=True,
        message="Logged out successfully. Discard the JWT bearer token on the client.",
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated User Profile",
    description="Returns the profile of the user identified by the Bearer token.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns the authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ==============================================================================
# RBAC Verification Endpoints (Used for testing and verifying role boundaries)
# ==============================================================================

@router.get(
    "/test/patient-only",
    summary="Patient-Only Access Verification",
    description="Internal endpoint accessible strictly by users with the PATIENT role.",
)
def test_patient_access(current_user: User = Depends(require_patient)):
    return {"message": "Welcome, patient", "user_id": str(current_user.id), "role": current_user.role.value}


@router.get(
    "/test/staff-only",
    summary="Staff-Only Access Verification",
    description="Internal endpoint accessible strictly by users with the STAFF role.",
)
def test_staff_access(current_user: User = Depends(require_staff)):
    return {"message": "Welcome, staff", "user_id": str(current_user.id), "role": current_user.role.value}


@router.get(
    "/test/admin-only",
    summary="Admin-Only Access Verification",
    description="Internal endpoint accessible strictly by users with the ADMIN role.",
)
def test_admin_access(current_user: User = Depends(require_admin)):
    return {"message": "Welcome, admin", "user_id": str(current_user.id), "role": current_user.role.value}
