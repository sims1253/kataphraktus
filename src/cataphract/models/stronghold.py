"""Stronghold model for the Cataphract game system.

This module contains the model for strongholds (towns, cities, fortresses)
which are key strategic locations that can be besieged and captured.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .faction import Faction
    from .game import Game
    from .map import Hex


class Stronghold(Base, TimestampCreatedMixin):
    """Represents a stronghold (town, city, or fortress).

    Strongholds are fortified locations that provide defensive bonuses,
    store supplies and loot, and can be besieged. They have thresholds
    that must be reduced to zero before they can be captured.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        name: Name of the stronghold
        hex_id: Foreign key to hex where stronghold is located
        type: Type of stronghold (town/city/fortress)
        controlling_faction_id: Faction that controls this stronghold
        defensive_bonus: Defensive bonus in battle (+3/+4/+5)
        base_threshold: Base siege threshold (10/15/20)
        current_threshold: Current siege threshold
        gates_open: Whether gates are open (allows entry without siege)
        supplies_held: Amount of supplies stored
        loot_held: Amount of loot stored
    """

    __tablename__ = "strongholds"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    controlling_faction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    # Stronghold attributes
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    defensive_bonus: Mapped[int] = mapped_column(Integer, nullable=False)
    base_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    current_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    gates_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supplies_held: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loot_held: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    hex: Mapped["Hex"] = relationship("Hex", back_populates="strongholds")
    controlling_faction: Mapped[Optional["Faction"]] = relationship(
        "Faction", back_populates="controlled_strongholds"
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_strongholds_game_name"),
        CheckConstraint("type IN ('town', 'city', 'fortress')", name="ck_strongholds_type"),
        Index("idx_strongholds_hex", "hex_id"),
        Index("idx_strongholds_faction", "controlling_faction_id"),
    )

    def __repr__(self) -> str:
        return f"<Stronghold(id={self.id}, name='{self.name}', type='{self.type}')>"
