"""Hospital entity model."""

from typing import List, Optional
from decimal import Decimal
from sqlalchemy import String, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Hospital(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Participating hospital organization."""
    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)

    # Relationships
    departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="hospital",
        cascade="all, delete-orphan",
    )
    staff_members: Mapped[List["User"]] = relationship(
        "User",
        back_populates="hospital",
    )

    def __repr__(self) -> str:
        return f"<Hospital id={self.id} name='{self.name}'>"
