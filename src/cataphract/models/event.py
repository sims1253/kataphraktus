"""Event model for the Cataphract game system.

This module contains the model for events, which record all significant
game occurrences for audit trail and player notification.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .game import Game


class Event(Base, TimestampCreatedMixin):
    """Represents a significant event in the game.

    Events are the audit trail and notification system for the game.
    They record battles, movements, foraging, morale checks, and all
    other significant occurrences.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        game_day: Game day when event occurred
        game_part: Daypart when event occurred
        timestamp: Real-world timestamp when event was recorded
        event_type: Type of event (battle/movement/foraging/etc)
        involved_entities: JSON with IDs of involved entities
        description: Human-readable description
        details: JSON with event-specific detailed data
        rand_source: JSON for deterministic RNG audit trail
        visible_to: JSON array of commander IDs who can see this event
        referee_notes: Notes for referee only
    """

    __tablename__ = "events"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)

    # Event timing
    game_day: Mapped[int] = mapped_column(Integer, nullable=False)
    game_part: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Event attributes
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    involved_entities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    rand_source: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    visible_to: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    referee_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="events")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "game_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_events_game_part",
        ),
        CheckConstraint(
            "event_type IN ('battle', 'siege_started', 'siege_ended', 'assault', 'stronghold_captured', "
            "'movement', 'foraging', 'torching', 'morale_check', 'revolt', 'harry', "
            "'army_split', 'army_merged', 'supplies_transferred', 'message_delivered', "
            "'commander_captured', 'commander_died', 'operation_completed', 'weather_change')",
            name="ck_events_type",
        ),
        Index("idx_events_game_time", "game_id", "game_day", "game_part"),
        Index("idx_events_type", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type='{self.event_type}', day={self.game_day}, part='{self.game_part}')>"
