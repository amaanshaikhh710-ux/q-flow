"""ArrivalPlan entity model — records travel-aware arrival and departure optimization recommendations."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, DateTime, Index, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, AwareDateTime


class ArrivalPlan(Base, UUIDPrimaryKeyMixin):
    """Immutable arrival plan snapshot mapping consultation window and travel to departure recommendations."""
    __tablename__ = "arrival_plans"
    __table_args__ = (
        Index("ix_arrival_plans_entry_created", "queue_entry_id", "created_at"),
        Index("ix_arrival_plans_pred_snap", "prediction_snapshot_id"),
    )

    queue_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("queue_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prediction_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    travel_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    travel_status: Mapped[str] = mapped_column(String(30), nullable=False, default="AVAILABLE")
    travel_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    travel_uncertainty_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    route_distance_meters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    driving_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    driving_distance_meters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bike_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bike_distance_meters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    walking_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    walking_distance_meters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    selected_travel_mode: Mapped[str] = mapped_column(String(30), default="DRIVE", nullable=False)
    arrival_buffer_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)

    # Windows
    consultation_start_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    consultation_end_at: Mapped[datetime] = mapped_column(AwareDateTime(), nullable=False)
    arrival_start_at: Mapped[Optional[datetime]] = mapped_column(AwareDateTime(), nullable=True)
    arrival_end_at: Mapped[Optional[datetime]] = mapped_column(AwareDateTime(), nullable=True)
    departure_start_at: Mapped[Optional[datetime]] = mapped_column(AwareDateTime(), nullable=True)
    departure_end_at: Mapped[Optional[datetime]] = mapped_column(AwareDateTime(), nullable=True)

    # Change tracking
    is_meaningful_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consultation_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    travel_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    queue_entry: Mapped["QueueEntry"] = relationship("QueueEntry", back_populates="arrival_plans")
    prediction_snapshot: Mapped["PredictionSnapshot"] = relationship("PredictionSnapshot", backref="arrival_plans")

    def __repr__(self) -> str:
        return (
            f"<ArrivalPlan id={self.id} entry_id={self.queue_entry_id} "
            f"departure={self.departure_start_at} arrival={self.arrival_start_at}>"
        )
