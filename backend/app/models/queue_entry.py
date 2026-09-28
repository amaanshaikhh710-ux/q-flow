"""QueueEntry entity model representing patient participation in a queue."""

import uuid
import enum
from datetime import datetime, date, time
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Integer, String, Numeric, ForeignKey, Enum, DateTime, Date, Time, UniqueConstraint, Index, Uuid, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin



class PriorityClass(str, enum.Enum):
    NORMAL = "normal"
    PRIORITY = "priority"
    EMERGENCY = "emergency"


class QueueEntryStatus(str, enum.Enum):
    CREATED = "CREATED"
    BOOKED = "BOOKED"
    ARRIVED = "ARRIVED"
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_CONSULTATION = "IN_CONSULTATION"
    COMPLETED = "COMPLETED"
    TEMPORARILY_LEFT = "TEMPORARILY_LEFT"
    RETURNED = "RETURNED"
    NO_SHOW = "NO_SHOW"


class QueueEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Patient queue ticket / entry in an active queue."""
    __tablename__ = "queue_entries"
    __table_args__ = (
        UniqueConstraint("queue_id", "appointment_date", "token_number", name="uq_queue_date_token_number"),
        Index("ix_queue_entries_queue_status", "queue_id", "status"),
        Index("ix_queue_entries_queue_date_token", "queue_id", "appointment_date", "token_number"),
        Index("ix_queue_entries_patient_created", "patient_user_id", "created_at"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=func.current_date(),
        server_default=func.current_date(),
        index=True,
    )
    # Booking provenance: each appointment retains the staff-authored schedule
    # that authorized it plus the selected consultation time.
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doctor_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    appointment_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_class: Mapped[PriorityClass] = mapped_column(
        Enum(PriorityClass, name="priority_class_enum", native_enum=False),
        default=PriorityClass.NORMAL,
        nullable=False,
        index=True,
    )
    status: Mapped[QueueEntryStatus] = mapped_column(
        Enum(QueueEntryStatus, name="queue_entry_status_enum", native_enum=False),
        default=QueueEntryStatus.CREATED,
        nullable=False,
        index=True,
    )
    booking_source: Mapped[str] = mapped_column(String(30), default="ONLINE", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # State machine transition timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    temporary_left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    no_show_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 5: Transient Travel Origin
    origin_latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    origin_longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    origin_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    travel_mode: Mapped[str] = mapped_column(String(30), default="DRIVE", nullable=False)
    travel_origin_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", back_populates="entries")
    patient: Mapped["User"] = relationship("User", back_populates="queue_entries")
    consultation: Mapped[Optional["Consultation"]] = relationship(
        "Consultation",
        back_populates="queue_entry",
        uselist=False,
        cascade="all, delete-orphan",
    )
    events: Mapped[List["QueueEvent"]] = relationship(
        "QueueEvent",
        back_populates="queue_entry",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="queue_entry",
        cascade="all, delete-orphan",
    )
    arrival_plans: Mapped[List["ArrivalPlan"]] = relationship(
        "ArrivalPlan",
        back_populates="queue_entry",
        cascade="all, delete-orphan",
    )
    prediction_snapshots: Mapped[List["PredictionSnapshot"]] = relationship(
        "PredictionSnapshot",
        back_populates="queue_entry",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<QueueEntry id={self.id} token={self.token_number} status='{self.status}'>"
