"""Queue entity model."""

import uuid
import enum
from datetime import date
from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, Enum, Uuid, Date, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class QueueStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Queue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Concurrent OPD patient queue."""
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("opd_session_id", "queue_date", name="uq_queue_session_date"),
        Index("ix_queues_date", "queue_date"),
    )

    opd_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("opd_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), default="Main Queue", nullable=False)
    # A queue is operationally scoped to one doctor session on one calendar date.
    queue_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today, index=True)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status_enum", native_enum=False),
        default=QueueStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    current_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Cached serving position; never the authoritative source of truth",
    )

    # Relationships
    opd_session: Mapped["OPDSession"] = relationship("OPDSession", back_populates="queues")
    entries: Mapped[List["QueueEntry"]] = relationship(
        "QueueEntry",
        back_populates="queue",
        cascade="all, delete-orphan",
    )
    events: Mapped[List["QueueEvent"]] = relationship(
        "QueueEvent",
        back_populates="queue",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Queue id={self.id} session_id={self.opd_session_id} status='{self.status}'>"
