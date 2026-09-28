"""User entity model."""

import uuid
from typing import List, Optional
import enum
from sqlalchemy import String, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    STAFF = "staff"
    ADMIN = "admin"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity with role-based access."""
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, index=True, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=False),
        default=UserRole.PATIENT,
        nullable=False,
        index=True,
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="staff_members")
    queue_entries: Mapped[List["QueueEntry"]] = relationship("QueueEntry", back_populates="patient")
    authored_events: Mapped[List["QueueEvent"]] = relationship("QueueEvent", back_populates="actor")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} name='{self.name}' role='{self.role}'>"
