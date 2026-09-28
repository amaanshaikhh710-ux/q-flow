"""Base model definitions and mixins for SQLAlchemy ORM."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func, Uuid
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AwareDateTime(TypeDecorator):
    """DateTime type that guarantees returned datetimes are UTC timezone-aware across all databases including SQLite."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc)
        return value


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class TimestampMixin:
    """Mixin for models requiring created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        AwareDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin providing a UUID primary key for entity tables."""
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
