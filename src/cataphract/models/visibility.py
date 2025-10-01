"""Visibility model for the Cataphract game system.

This module contains the model for commander visibility, which caches
what each commander can see for performance.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .commander import Commander


class CommanderVisibility(Base):
    """Represents cached visibility data for a commander.

    This table caches what hexes, armies, and strongholds a commander
    can see at a specific game time. This improves performance for
    fog-of-war queries.

    Attributes:
        id: Primary key
        commander_id: Foreign key to commander
        game_day: Game day for this visibility snapshot
        game_part: Daypart for this visibility snapshot
        visible_hex_ids: JSON array of visible hex IDs
        discovered_hexes: JSON object mapping hex IDs to first discovery day
        known_armies: JSON with simplified army data visible to commander
        known_strongholds: JSON with simplified stronghold data visible to commander
        last_updated_timestamp: Real-world timestamp when last updated
    """

    __tablename__ = "commander_visibility"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)

    # Visibility snapshot timing
    game_day: Mapped[int] = mapped_column(Integer, nullable=False)
    game_part: Mapped[str] = mapped_column(String, nullable=False)

    # Visibility data
    visible_hex_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    discovered_hexes: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    known_armies: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    known_strongholds: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    commander: Mapped["Commander"] = relationship("Commander")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("commander_id", "game_day", "game_part", name="uq_commander_visibility"),
        CheckConstraint(
            "game_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_commander_visibility_game_part",
        ),
        Index("idx_visibility_lookup", "commander_id", "game_day", "game_part"),
        Index("idx_visibility_commander", "commander_id"),
    )

    def __repr__(self) -> str:
        return f"<CommanderVisibility(commander={self.commander_id}, day={self.game_day}, part='{self.game_part}')>"
