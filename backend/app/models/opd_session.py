"""OPD Session entity model."""

import uuid
import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, Enum, DateTime, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OPDSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational OPD shift/session for a doctor."""
    __tablename__ = "opd_sessions"
    __table_args__ = (
        Index("ix_opd_sessions_doctor_starts_at", "doctor_id", "starts_at"),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum", native_enum=False),
        default=SessionStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    # Relationships
    department: Mapped["Department"] = relationship("Department", back_populates="opd_sessions")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="opd_sessions")
    queues: Mapped[List["Queue"]] = relationship(
        "Queue",
        back_populates="opd_session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<OPDSession id={self.id} doctor_id={self.doctor_id} status='{self.status}'>"
