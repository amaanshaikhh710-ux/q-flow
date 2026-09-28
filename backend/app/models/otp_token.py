"""OTP Token entity model for passwordless authentication and verification."""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin


class OTPToken(Base, UUIDPrimaryKeyMixin):
    """Temporary one-time password tokens for patient authentication."""
    __tablename__ = "otp_tokens"
    __table_args__ = (
        Index("ix_otp_tokens_recipient_verified", "recipient", "is_verified"),
    )

    recipient: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    otp_code: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), default="LOGIN", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OTPToken id={self.id} recipient='{self.recipient}' verified={self.is_verified}>"
