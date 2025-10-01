"""Commander and trait models for the Cataphract game system.

This module contains models for:
- Commanders (the leaders who command armies)
- Traits (catalog of available traits)
- CommanderTraits (which traits each commander has)
"""

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
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
    from .army import Army
    from .faction import Faction
    from .game import Game
    from .map import Hex
    from .message import Message
    from .player import Player


class Commander(Base, TimestampCreatedMixin):
    """Represents a commander in the game.

    Commanders are the key actors in the game, leading armies and making
    strategic decisions. They have traits that affect their capabilities
    and can have family relationships with other commanders.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        player_id: Foreign key to player controlling this commander
        faction_id: Foreign key to faction this commander belongs to
        name: Name of the commander
        age: Age of the commander (minimum 14)
        relationship_type: Type of relationship to another commander
        related_to_commander_id: Foreign key to related commander
        current_hex_id: Foreign key to hex where commander is located
        status: Current status (active/captured/dead)
        captured_by_faction_id: Faction that captured this commander (if captured)
    """

    __tablename__ = "commanders"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    player_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    faction_id: Mapped[int] = mapped_column(Integer, ForeignKey("factions.id"), nullable=False)
    related_to_commander_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=True
    )
    current_hex_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hexes.id"), nullable=True
    )
    captured_by_faction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    # Commander attributes
    name: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="commanders")
    player: Mapped[Optional["Player"]] = relationship("Player", back_populates="commanders")
    faction: Mapped["Faction"] = relationship(
        "Faction",
        back_populates="commanders",
        foreign_keys=[faction_id],
    )
    related_to: Mapped[Optional["Commander"]] = relationship(
        "Commander",
        remote_side=[id],
        foreign_keys=[related_to_commander_id],
    )
    current_hex: Mapped[Optional["Hex"]] = relationship("Hex")
    captured_by_faction: Mapped[Optional["Faction"]] = relationship(
        "Faction", foreign_keys=[captured_by_faction_id]
    )
    armies: Mapped[list["Army"]] = relationship("Army", back_populates="commander")
    traits: Mapped[list["CommanderTrait"]] = relationship(
        "CommanderTrait", back_populates="commander", cascade="all, delete-orphan"
    )
    messages_sent: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_commander_id",
    )
    messages_received: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="recipient",
        foreign_keys="Message.recipient_commander_id",
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint("age >= 14", name="ck_commanders_age"),
        CheckConstraint("status IN ('active', 'captured', 'dead')", name="ck_commanders_status"),
        Index("idx_commanders_player", "player_id"),
        Index("idx_commanders_faction", "faction_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Commander(id={self.id}, name='{self.name}', age={self.age}, status='{self.status}')>"
        )


class Trait(Base, TimestampCreatedMixin):
    """Represents a trait that commanders can have.

    This is a catalog table that defines all available traits in the game.
    Traits provide various bonuses and modifications to commander capabilities.

    Attributes:
        id: Primary key
        name: Unique name of the trait
        description: Description of what the trait does
        scope_tags: JSON array of scope tags (e.g., ["battle_mod", "logistics_mod"])
        effect_data: JSON object with structured effect data
        ruleset_version: Version of ruleset this trait belongs to
        content_pack: Content pack this trait belongs to (NULL for base game)
    """

    __tablename__ = "traits"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Trait attributes
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    scope_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    effect_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String, nullable=False, default="1.1")
    content_pack: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    commander_traits: Mapped[list["CommanderTrait"]] = relationship(
        "CommanderTrait", back_populates="trait"
    )

    # Table constraints
    __table_args__ = (Index("idx_traits_content_pack", "content_pack"),)

    def __repr__(self) -> str:
        return f"<Trait(id={self.id}, name='{self.name}')>"


class CommanderTrait(Base):
    """Represents a trait assigned to a commander.

    This is a join table that links commanders to their traits and tracks
    when they acquired each trait.

    Attributes:
        id: Primary key
        commander_id: Foreign key to commander
        trait_id: Foreign key to trait
        acquired_at_age: Age when commander acquired this trait
        instance_data: JSON for traits with variable effects (future use)
    """

    __tablename__ = "commander_traits"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)
    trait_id: Mapped[int] = mapped_column(Integer, ForeignKey("traits.id"), nullable=False)

    # Trait acquisition
    acquired_at_age: Mapped[int] = mapped_column(Integer, nullable=False)
    instance_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    commander: Mapped["Commander"] = relationship("Commander", back_populates="traits")
    trait: Mapped["Trait"] = relationship("Trait", back_populates="commander_traits")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("commander_id", "trait_id", name="uq_commander_traits"),
        Index("idx_commander_traits_commander", "commander_id"),
        Index("idx_commander_traits_trait", "trait_id"),
    )

    def __repr__(self) -> str:
        return f"<CommanderTrait(commander={self.commander_id}, trait={self.trait_id}, acquired_at={self.acquired_at_age})>"
