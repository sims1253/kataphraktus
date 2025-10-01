"""Naval models for the Cataphract game system.

This module contains models for:
- ShipTypes (catalog of available ship types)
- Ships (individual ships in the game)
"""

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
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
    from .faction import Faction
    from .game import Game
    from .map import Hex


class ShipType(Base):
    """Represents a type of ship.

    This is a catalog table that defines all available ship types in the game.
    Ship types have different capacities, costs, and capabilities.

    Attributes:
        id: Primary key
        name: Unique name of the ship type
        capacity_soldiers: Soldier capacity
        capacity_cavalry: Cavalry capacity (cavalry take more space)
        capacity_supplies: Supply capacity
        daily_cost_loot: Daily cost in loot per ship
        can_sea: Whether ship can travel on sea hexes
        can_river: Whether ship can travel on river hexes
        content_pack: Content pack this ship type belongs to (NULL for base game)
        special_rules: JSON with special rules (e.g., shallow_water_only)
    """

    __tablename__ = "ship_types"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Ship type attributes
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    capacity_soldiers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_cavalry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_supplies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_cost_loot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_sea: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_river: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_pack: Mapped[str | None] = mapped_column(String, nullable=True)
    special_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    ships: Mapped[list["Ship"]] = relationship("Ship", back_populates="ship_type")

    def __repr__(self) -> str:
        return f"<ShipType(id={self.id}, name='{self.name}')>"


class Ship(Base, TimestampCreatedMixin):
    """Represents an individual ship in the game.

    Ships can transport armies and their supplies across water hexes.
    They have morale and can flee from combat.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        controlling_faction_id: Foreign key to faction controlling this ship
        current_hex_id: Foreign key to current hex location
        ship_type_id: Foreign key to ship type
        has_siege_equipment: Whether ship carries siege equipment
        embarked_army_id: Foreign key to embarked army (if any)
        morale: Ship morale
        status: Ship status (available/transporting/fled)
        return_day: Game day when fled ship returns
    """

    __tablename__ = "ships"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    controlling_faction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("factions.id"), nullable=False
    )
    current_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    ship_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("ship_types.id"), nullable=False)
    embarked_army_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("armies.id"), nullable=True
    )

    # Ship attributes
    has_siege_equipment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    morale: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    status: Mapped[str] = mapped_column(String, nullable=False)
    return_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    controlling_faction: Mapped["Faction"] = relationship("Faction")
    current_hex: Mapped["Hex"] = relationship("Hex")
    ship_type: Mapped["ShipType"] = relationship("ShipType", back_populates="ships")
    embarked_army: Mapped[Optional["Army"]] = relationship("Army")

    # Table constraints
    __table_args__ = (
        CheckConstraint("status IN ('available', 'transporting', 'fled')", name="ck_ships_status"),
        Index("idx_ships_hex", "current_hex_id"),
        Index("idx_ships_army", "embarked_army_id"),
    )

    def __repr__(self) -> str:
        return f"<Ship(id={self.id}, type={self.ship_type_id}, status='{self.status}')>"
