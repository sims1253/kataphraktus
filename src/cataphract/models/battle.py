"""Battle model for the Cataphract game system.

This module contains the model for battles, which record combat
outcomes between armies.
"""

from typing import TYPE_CHECKING, Any

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
    from .event import Event
    from .game import Game
    from .map import Hex


class Battle(Base, TimestampCreatedMixin):
    """Represents a battle between armies.

    Battles are field battles, assaults on strongholds, or naval battles.
    They record rolls, casualties, morale changes, and outcomes.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        event_id: Foreign key to corresponding event
        game_day: Game day when battle occurred
        hex_id: Foreign key to hex where battle occurred
        battle_type: Type of battle (field/assault/naval)
        attacker_side: JSON array of attacking army IDs
        defender_side: JSON array of defending army IDs
        attacker_rolls: JSON with attacker rolls and modifiers
        defender_rolls: JSON with defender rolls and modifiers
        victor_side: Which side won (attacker/defender)
        roll_difference: Difference in battle rolls
        casualties: JSON with casualty details per army
        morale_changes: JSON with morale changes per army
        commanders_captured: JSON array of captured commander IDs
        loot_captured: Amount of loot captured by victor
        routed_armies: JSON array of routed army IDs
    """

    __tablename__ = "battles"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"), nullable=False)
    hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)

    # Battle attributes
    game_day: Mapped[int] = mapped_column(Integer, nullable=False)
    battle_type: Mapped[str] = mapped_column(String, nullable=False)
    attacker_side: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    defender_side: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    attacker_rolls: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    defender_rolls: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    victor_side: Mapped[str] = mapped_column(String, nullable=False)
    roll_difference: Mapped[int] = mapped_column(Integer, nullable=False)
    casualties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    morale_changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    commanders_captured: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    loot_captured: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    routed_armies: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    event: Mapped["Event"] = relationship("Event")
    hex: Mapped["Hex"] = relationship("Hex")

    # Table constraints
    __table_args__ = (
        CheckConstraint("battle_type IN ('field', 'assault', 'naval')", name="ck_battles_type"),
        CheckConstraint("victor_side IN ('attacker', 'defender')", name="ck_battles_victor"),
        Index("idx_battles_hex", "hex_id"),
        Index("idx_battles_day", "game_id", "game_day"),
    )

    def __repr__(self) -> str:
        return f"<Battle(id={self.id}, type='{self.battle_type}', day={self.game_day}, victor='{self.victor_side}')>"
