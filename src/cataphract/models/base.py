"""Base model class and common mixins for SQLAlchemy models.

This module provides the declarative base for all models and common patterns
used throughout the Cataphract database schema.
"""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides type_annotation_map for automatic type inference from Python types.
    """

    # Configure automatic type mapping
    type_annotation_map: ClassVar[dict] = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """Mixin for models that need created_at and updated_at timestamps.

    Automatically sets created_at on insert and updated_at on update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TimestampCreatedMixin:
    """Mixin for models that only need created_at timestamp.

    Use this for immutable records that don't need updated_at.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def utc_now() -> datetime:
    """Get current UTC time with timezone awareness.

    Returns:
        datetime: Current time in UTC with timezone info
    """
    return datetime.now(UTC)
