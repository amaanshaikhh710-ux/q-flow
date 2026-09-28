"""Notification entity model — delivery tracking and audit log."""

import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Index, func, Uuid, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin


class NotificationChannel(str, enum.Enum):
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    WEB = "WEB"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class Notification(Base, UUIDPrimaryKeyMixin):
    """Outbound notification log for patient updates and real-time alerts."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_status_created", "status", "created_at"),
        UniqueConstraint("queue_entry_id", "trigger_event_id", "notification_type", name="uq_notifications_entry_trigger_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    queue_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=NotificationStatus.PENDING, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    queue_entry: Mapped[Optional["QueueEntry"]] = relationship("QueueEntry", back_populates="notifications")
    trigger_event: Mapped[Optional["QueueEvent"]] = relationship("QueueEvent")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} channel='{self.channel}' status='{self.status}'>"
