"""Doctor entity model."""

import uuid
import enum
from typing import List
from sqlalchemy import String, ForeignKey, Enum, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class DoctorStatus(str, enum.Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BREAK = "break"


class Doctor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Clinical doctor provider entity."""
    __tablename__ = "doctors"

    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[DoctorStatus] = mapped_column(
        Enum(DoctorStatus, name="doctor_status_enum", native_enum=False),
        default=DoctorStatus.AVAILABLE,
        nullable=False,
        index=True,
    )

    # Relationships
    department: Mapped["Department"] = relationship("Department", back_populates="doctors")
    opd_sessions: Mapped[List["OPDSession"]] = relationship("OPDSession", back_populates="doctor")
    consultations: Mapped[List["Consultation"]] = relationship("Consultation", back_populates="doctor")

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name='{self.name}' status='{self.status}'>"
