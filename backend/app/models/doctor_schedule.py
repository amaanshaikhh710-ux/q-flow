"""Doctor schedule entity model for date-specific and time-specific clinical scheduling."""

import uuid
from datetime import date, time
from typing import Optional
from sqlalchemy import Date, Time, String, ForeignKey, UniqueConstraint, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class DoctorSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational OPD shift and clinical schedule for a doctor on a specific calendar date."""
    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint("doctor_id", "schedule_date", name="uq_doctor_schedule_date"),
        Index("ix_doctor_schedules_hosp_date", "hospital_id", "schedule_date"),
        Index("ix_doctor_schedules_doc_date", "doctor_id", "schedule_date"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)  # e.g., 09:00:00
    end_time: Mapped[time] = mapped_column(Time, nullable=False)    # e.g., 13:00:00
    status: Mapped[str] = mapped_column(String(30), default="AVAILABLE", nullable=False)  # AVAILABLE, UNAVAILABLE
    created_by_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    opd_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("opd_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital")
    doctor: Mapped["Doctor"] = relationship("Doctor", backref="schedules")
    department: Mapped["Department"] = relationship("Department")
    created_by: Mapped[Optional["User"]] = relationship("User")
    opd_session: Mapped[Optional["OPDSession"]] = relationship("OPDSession")

    def __repr__(self) -> str:
        return (
            f"<DoctorSchedule doctor_id={self.doctor_id} date={self.schedule_date} "
            f"time={self.start_time}-{self.end_time} status={self.status}>"
        )
