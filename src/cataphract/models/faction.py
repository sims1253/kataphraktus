"""Faction models for the Cataphract game system.

This module contains models for factions (the major powers in the game)
and their relationships with each other.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .commander import Commander
    from .game import Game
    from .map import Hex
    from .stronghold import Stronghold


class Faction(Base, TimestampCreatedMixin):
    """Represents a faction in the game.

    A faction is a major power with commanders, armies, and territory.
    Each faction has special rules, unique units, and diplomatic relations
    with other factions.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        name: Name of the faction
        description: Description of the faction
        color: Hex color code for map display
        special_rules: JSON object with faction-specific rules
        unique_units: JSON array of unique unit type names
    """

    __tablename__ = "factions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)

    # Faction attributes
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str] = mapped_column(String, nullable=False)
    special_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    unique_units: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="factions")
    commanders: Mapped[list["Commander"]] = relationship(
        "Commander", back_populates="faction", foreign_keys="Commander.faction_id"
    )
    controlled_hexes: Mapped[list["Hex"]] = relationship(
        "Hex", back_populates="controlling_faction"
    )
    controlled_strongholds: Mapped[list["Stronghold"]] = relationship(
        "Stronghold", back_populates="controlling_faction"
    )
    relations_from: Mapped[list["FactionRelation"]] = relationship(
        "FactionRelation",
        back_populates="faction",
        foreign_keys="FactionRelation.faction_id",
        cascade="all, delete-orphan",
    )
    relations_to: Mapped[list["FactionRelation"]] = relationship(
        "FactionRelation",
        back_populates="other_faction",
        foreign_keys="FactionRelation.other_faction_id",
        cascade="all, delete-orphan",
    )

    # Table constraints
    __table_args__ = (UniqueConstraint("game_id", "name", name="uq_factions_game_name"),)

    def __repr__(self) -> str:
        return f"<Faction(id={self.id}, name='{self.name}')>"


class FactionRelation(Base):
    """Represents diplomatic relations between two factions.

    Tracks the relationship type (allied/neutral/hostile) and when
    it was established.

    Attributes:
        id: Primary key
        faction_id: Foreign key to the first faction
        other_faction_id: Foreign key to the second faction
        relation_type: Type of relationship (allied/neutral/hostile)
        since_day: Game day when this relationship began
    """

    __tablename__ = "faction_relations"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    faction_id: Mapped[int] = mapped_column(Integer, ForeignKey("factions.id"), nullable=False)
    other_faction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factions.id"), nullable=False
    )

    # Relation attributes
    relation_type: Mapped[str] = mapped_column(String, nullable=False)
    since_day: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    faction: Mapped["Faction"] = relationship(
        "Faction", back_populates="relations_from", foreign_keys=[faction_id]
    )
    other_faction: Mapped["Faction"] = relationship(
        "Faction", back_populates="relations_to", foreign_keys=[other_faction_id]
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint("faction_id", "other_faction_id", name="uq_faction_relations"),
        CheckConstraint(
            "relation_type IN ('allied', 'neutral', 'hostile')",
            name="ck_faction_relations_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<FactionRelation(faction={self.faction_id}, other={self.other_faction_id}, type='{self.relation_type}')>"
