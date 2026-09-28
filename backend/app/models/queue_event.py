"""QueueEvent entity model — append-only audit & operational event log."""

import uuid
import enum
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, ForeignKey, DateTime, Index, JSON, func, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin


class QueueEventType(str, enum.Enum):
    TOKEN_CREATED = "TOKEN_CREATED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    PATIENT_JOINED = "PATIENT_JOINED"
    PATIENT_CHECKED_IN = "PATIENT_CHECKED_IN"
    PATIENT_ARRIVED = "PATIENT_ARRIVED"
    PATIENT_CALLED = "PATIENT_CALLED"
    CONSULTATION_STARTED = "CONSULTATION_STARTED"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    EMERGENCY_INSERTED = "EMERGENCY_INSERTED"
    DOCTOR_BREAK_STARTED = "DOCTOR_BREAK_STARTED"
    DOCTOR_BREAK_ENDED = "DOCTOR_BREAK_ENDED"
    DOCTOR_DELAY = "DOCTOR_DELAY"
    QUEUE_PAUSED = "QUEUE_PAUSED"
    QUEUE_RESUMED = "QUEUE_RESUMED"
    PATIENT_NO_SHOW = "PATIENT_NO_SHOW"
    PATIENT_TEMPORARILY_LEFT = "PATIENT_TEMPORARILY_LEFT"
    PATIENT_RETURNED = "PATIENT_RETURNED"
    STAFF_REQUEUES = "STAFF_REQUEUES"
    DOCTOR_UNAVAILABLE = "DOCTOR_UNAVAILABLE"
    DOCTOR_AVAILABLE = "DOCTOR_AVAILABLE"
    QUEUE_CLOSED = "QUEUE_CLOSED"


class QueueEvent(Base, UUIDPrimaryKeyMixin):
    """Append-only operational event log for queue reconstruction, audit, and ML training."""
    __tablename__ = "queue_events"
    __table_args__ = (
        Index("ix_queue_events_queue_time", "queue_id", "event_time"),
        Index("ix_queue_events_entry_time", "queue_entry_id", "event_time"),
        Index("ix_queue_events_type_time", "event_type", "event_time"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    queue_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_entries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
        doc="Structured event data stored as PostgreSQL JSONB",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", back_populates="events")
    queue_entry: Mapped[Optional["QueueEntry"]] = relationship("QueueEntry", back_populates="events")
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="authored_events")

    def __repr__(self) -> str:
        return f"<QueueEvent id={self.id} type='{self.event_type}' time={self.event_time}>"
