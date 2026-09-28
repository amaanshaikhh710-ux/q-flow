"""PredictionSnapshot entity model — immutable forecast log with uncertainty and explainability."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, DateTime, Index, JSON, func, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, AwareDateTime


class PredictionSnapshot(Base, UUIDPrimaryKeyMixin):
    """Immutable prediction snapshot storing consultation windows, features, and explanations."""
    __tablename__ = "prediction_snapshots"
    __table_args__ = (
        Index("ix_prediction_snapshots_entry_created", "queue_entry_id", "created_at"),
        Index("ix_prediction_snapshots_queue_created", "queue_id", "created_at"),
        Index("ix_prediction_snapshots_trigger_event", "trigger_event_id"),
    )

    queue_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predicted_start_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    predicted_end_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    predicted_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    uncertainty_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    model_type: Mapped[str] = mapped_column(String(60), nullable=False, default="robust_median")
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="baseline-v1")
    prediction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="VALID")
    explanation_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    feature_snapshot_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    trigger_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_meaningful_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shift_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", backref="prediction_snapshots")
    queue_entry: Mapped["QueueEntry"] = relationship("QueueEntry", back_populates="prediction_snapshots")
    trigger_event: Mapped[Optional["QueueEvent"]] = relationship("QueueEvent", backref="triggered_predictions")

    @property
    def uncertainty_margin_seconds(self) -> int:
        """Uncertainty margin buffer in seconds (non-negative, minimum 180s)."""
        return max(180, int(self.uncertainty_minutes * 60))

    @property
    def patients_ahead_count(self) -> int:
        """Count of active unserviced patients ahead in queue."""
        if self.feature_snapshot_json and isinstance(self.feature_snapshot_json, dict):
            return max(0, int(self.feature_snapshot_json.get("patients_ahead", 0)))
        return 0

    @property
    def explanation(self) -> Optional[str]:
        """Patient-facing explanation for estimate or ETA update."""
        return self.explanation_text

    def __repr__(self) -> str:
        return (
            f"<PredictionSnapshot id={self.id} entry_id={self.queue_entry_id} "
            f"start={self.predicted_start_at} end={self.predicted_end_at}>"
        )

