"""Pydantic schemas for authentication and user accounts."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from app.models.user import UserRole


class UserRegisterRequest(BaseModel):
    """Schema for public patient registration."""
    name: str = Field(..., min_length=1, max_length=150, description="Full name of the patient")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Phone number with country code")
    password: str = Field(..., min_length=6, max_length=128, description="Account password (min 6 characters)")
    role: Optional[str] = Field(None, description="Forbidden for public escalation; always coerced to patient")

    @model_validator(mode="after")
    def validate_contact_info(self) -> "UserRegisterRequest":
        """Ensures at least one contact method (email or phone) is provided."""
        if not self.email and not self.phone:
            raise ValueError("At least one contact method (email or phone) must be provided")
        return self


class LoginRequest(BaseModel):
    """Schema for user login using email or phone as identifier."""
    identifier: str = Field(..., min_length=1, description="Registered email address or phone number")
    password: str = Field(..., min_length=1, description="Account password")


class UserResponse(BaseModel):
    """Safe public user information (password_hash is strictly omitted)."""
    id: uuid.UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    hospital_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Response payload containing JWT access token and user profile."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token validity duration in seconds")
    user: UserResponse


class LogoutResponse(BaseModel):
    """Response payload for client logout."""
    success: bool = True
    message: str = "Logged out successfully. Discard the JWT bearer token on the client."


class OTPRequestPayload(BaseModel):
    """Schema for requesting a one-time password."""
    recipient: str = Field(..., min_length=4, max_length=255, description="Mobile number or email address")
    channel: str = Field("SMS", description="Delivery channel ('SMS' or 'EMAIL')")
    purpose: str = Field("LOGIN", description="Purpose: 'LOGIN' or 'REGISTRATION'")


class OTPRequestResponse(BaseModel):
    """Response returned upon OTP request."""
    success: bool = True
    recipient: str
    message: str
    channel: str
    delivery_status: str = Field("SENT", description="'SENT' if provider configured, or 'CONFIGURATION_REQUIRED'")
    expires_in_seconds: int = 300
    dev_hint: Optional[str] = None


class OTPVerifyPayload(BaseModel):
    """Schema for verifying a one-time password and logging in or registering."""
    recipient: str = Field(..., min_length=4, max_length=255, description="Mobile number or email address")
    otp_code: str = Field(..., min_length=4, max_length=10, description="6-digit OTP code")
    name: Optional[str] = Field(None, description="Patient name if registering for the first time")

