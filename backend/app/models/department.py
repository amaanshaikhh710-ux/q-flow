"""Department entity model."""

import uuid
from typing import List
from sqlalchemy import String, ForeignKey, UniqueConstraint, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Clinical OPD department within a hospital."""
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("hospital_id", "name", name="uq_department_hospital_name"),
        Index("ix_departments_hospital_name", "hospital_id", "name"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="departments")
    doctors: Mapped[List["Doctor"]] = relationship(
        "Doctor",
        back_populates="department",
        cascade="all, delete-orphan",
    )
    opd_sessions: Mapped[List["OPDSession"]] = relationship(
        "OPDSession",
        back_populates="department",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} hospital_id={self.hospital_id} name='{self.name}'>"
