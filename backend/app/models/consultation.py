"""Consultation entity model — dedicated normalized table for service durations (DEC-031)."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, Text, ForeignKey, DateTime, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Consultation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized clinical consultation record.

    DEC-031: This table is the single authoritative source of truth for
    clinical consultation lifecycle data and actual service durations.
    """
    __tablename__ = "consultations"
    __table_args__ = (
        Index("ix_consultations_doctor_started_at", "doctor_id", "started_at"),
        Index("ix_consultations_queue_entry", "queue_entry_id"),
    )

    queue_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_entries.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Actual elapsed clinical duration in seconds upon completion",
    )
    interruption_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Operational interruption notes for outlier classification",
    )

    # Relationships
    queue_entry: Mapped["QueueEntry"] = relationship("QueueEntry", back_populates="consultation")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="consultations")

    def __repr__(self) -> str:
        return f"<Consultation id={self.id} doctor_id={self.doctor_id} duration={self.duration_seconds}s>"
