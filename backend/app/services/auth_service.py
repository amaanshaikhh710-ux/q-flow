import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User, UserRole
from app.models.otp_token import OTPToken
from app.schemas.auth import (
    UserRegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    OTPRequestPayload,
    OTPRequestResponse,
    OTPVerifyPayload,
)
from app.services.notifications.service import get_notification_provider
from app.services.notifications.twilio_provider import TwilioNotificationProvider


class AuthService:
    """Service handling user registration, authentication, OTP, and session token generation."""

    @staticmethod
    def register_patient(db: Session, request: UserRegisterRequest) -> User:
        """Register a new patient account.

        Enforces that public registration ONLY creates PATIENT accounts.
        Rejects duplicate email or phone numbers.
        """
        # Duplicate email check
        if request.email:
            existing_email = db.query(User).filter(User.email == request.email).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this email address already exists",
                )

        # Duplicate phone check
        if request.phone:
            existing_phone = db.query(User).filter(User.phone == request.phone).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this phone number already exists",
                )

        # Secure password hashing (bcrypt)
        hashed_pw = hash_password(request.password)

        # Enforce PATIENT role strictly for public registration
        new_user = User(
            name=request.name.strip(),
            email=request.email,
            phone=request.phone.strip() if request.phone else None,
            password_hash=hashed_pw,
            role=UserRole.PATIENT,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def authenticate_user(db: Session, request: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue a signed JWT access token."""
        identifier = request.identifier.strip()

        # Match either email or phone
        user: Optional[User] = (
            db.query(User)
            .filter(or_(User.email == identifier, User.phone == identifier))
            .first()
        )

        # Generic error message to prevent enumeration
        if not user or not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Issue JWT with identity and role
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
        )

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def request_otp(db: Session, request: OTPRequestPayload) -> OTPRequestResponse:
        """Generate and dispatch a 6-digit OTP code with 5-minute validity."""
        recipient = request.recipient.strip()
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=5)

        token_record = OTPToken(
            recipient=recipient,
            otp_code=otp_code,
            purpose=request.purpose,
            expires_at=expires_at,
            is_verified=False,
        )
        db.add(token_record)
        db.commit()
        db.refresh(token_record)

        # Determine if external SMS/notification provider is actively configured
        provider = get_notification_provider()
        delivery_status = "SENT"
        dev_hint = None

        if isinstance(provider, TwilioNotificationProvider):
            if not provider.is_configured:
                delivery_status = "CONFIGURATION_REQUIRED"
                dev_hint = f"Dev OTP: {otp_code} (Twilio not configured)"
            else:
                try:
                    provider.send(
                        notification_id=token_record.id,
                        recipient=recipient,
                        title="Your Q-FLOW Verification Code",
                        message=f"Your Q-FLOW verification code is: {otp_code}. Valid for 5 minutes.",
                        channel="SMS",
                    )
                except Exception:
                    delivery_status = "FAILED"
        else:
            # Mock / development provider
            delivery_status = "CONFIGURATION_REQUIRED" if not settings.is_production else "FAILED"
            dev_hint = f"Dev OTP: {otp_code}"

        return OTPRequestResponse(
            success=True,
            recipient=recipient,
            channel=request.channel,
            message=f"Verification code generated for {recipient}.",
            delivery_status=delivery_status,
            expires_in_seconds=300,
            dev_hint=dev_hint,
        )

    @staticmethod
    def verify_otp(db: Session, request: OTPVerifyPayload) -> TokenResponse:
        """Verify OTP code, authenticate or register the patient, and return JWT token."""
        recipient = request.recipient.strip()
        code = request.otp_code.strip()
        now = datetime.now(timezone.utc)

        # Find matching token
        token_record = (
            db.query(OTPToken)
            .filter(
                OTPToken.recipient == recipient,
                OTPToken.otp_code == code,
                OTPToken.is_verified == False,
            )
            .order_by(OTPToken.created_at.desc())
            .first()
        )

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code. Please verify the code or request a new one.",
            )

        # Expiry check
        token_expiry = token_record.expires_at
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)

        if token_expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP code has expired. Please request a new one.",
            )

        # Mark OTP as consumed/verified
        token_record.is_verified = True

        # Find or create user
        is_email = "@" in recipient
        user = (
            db.query(User)
            .filter(User.email == recipient if is_email else User.phone == recipient)
            .first()
        )

        if not user:
            # Register new patient via OTP
            name = request.name.strip() if request.name else f"Patient {recipient[-4:]}"
            random_pw = secrets.token_hex(16)
            user = User(
                name=name,
                email=recipient if is_email else None,
                phone=recipient if not is_email else None,
                password_hash=hash_password(random_pw),
                role=UserRole.PATIENT,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        # Issue JWT
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
        )
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
        )
