"""Doctor availability model for date-specific operational scheduling."""

import uuid
from datetime import date
from typing import Optional
from sqlalchemy import Date, Boolean, String, ForeignKey, UniqueConstraint, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class DoctorAvailability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit doctor availability override per calendar date."""
    __tablename__ = "doctor_availability"
    __table_args__ = (
        UniqueConstraint("doctor_id", "availability_date", name="uq_doctor_date_availability"),
        Index("ix_doctor_avail_doc_date", "doctor_id", "availability_date"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    availability_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", backref="availability_overrides")

    def __repr__(self) -> str:
        return f"<DoctorAvailability doctor_id={self.doctor_id} date={self.availability_date} available={self.is_available}>"
