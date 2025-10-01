"""Siege model for the Cataphract game system.

This module contains the model for sieges, which track the process
of besieging and capturing strongholds.
"""

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .army import Army
    from .game import Game
    from .stronghold import Stronghold


class Siege(Base, TimestampCreatedMixin):
    """Represents a siege of a stronghold.

    Sieges track the process of reducing a stronghold's threshold to zero
    through attrition, disease, and siege engines. They can end with
    gates opening, capture, or the siege being lifted.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        stronghold_id: Foreign key to stronghold being sieged
        attacker_armies: JSON array of attacking army IDs
        defender_army_id: Foreign key to defending army (if any)
        started_on_day: Game day when siege started
        weeks_elapsed: Number of weeks siege has been ongoing
        current_threshold: Current threshold value
        threshold_modifiers: JSON with threshold modifiers
        siege_engines_count: Number of siege engines
        assault_attempts: JSON array of battle IDs for assault attempts
        status: Siege status (ongoing/gates_opened/captured/lifted)
        ended_on_day: Game day when siege ended
    """

    __tablename__ = "sieges"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    stronghold_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strongholds.id"), nullable=False
    )
    defender_army_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("armies.id"), nullable=True
    )

    # Siege attributes
    attacker_armies: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    started_on_day: Mapped[int] = mapped_column(Integer, nullable=False)
    weeks_elapsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_modifiers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    siege_engines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assault_attempts: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    ended_on_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    stronghold: Mapped["Stronghold"] = relationship("Stronghold")
    defender_army: Mapped[Optional["Army"]] = relationship("Army")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('ongoing', 'gates_opened', 'captured', 'lifted')",
            name="ck_sieges_status",
        ),
        Index("idx_sieges_stronghold", "stronghold_id"),
        Index("idx_sieges_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Siege(id={self.id}, stronghold={self.stronghold_id}, status='{self.status}')>"
