"""Army and unit models for the Cataphract game system.

This module contains models for:
- Armies (groups of military units under a commander)
- UnitTypes (catalog of available unit types)
- Detachments (individual military units within an army)
- MovementLegs (army movement itinerary for tracking mid-daypart interruptions)
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import Base, TimestampCreatedMixin, TimestampMixin

if TYPE_CHECKING:
    from .commander import Commander
    from .game import Game
    from .map import Hex
    from .order import Order
    from .stronghold import Stronghold


class Army(Base, TimestampMixin):
    """Represents an army in the game.

    An army is a collection of detachments led by a commander. It has
    supplies, morale, and can perform various actions like moving,
    foraging, and fighting.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        commander_id: Foreign key to commander leading this army
        name: Name of the army (optional)
        current_hex_id: Foreign key to current hex location
        destination_hex_id: Foreign key to destination hex (if moving)
        movement_points_remaining: Remaining movement points
        morale_current: Current morale level
        morale_resting: Resting morale (recovers to this)
        morale_max: Maximum morale
        supplies_current: Current supplies
        supplies_capacity: Maximum supplies capacity
        daily_consumption: Supplies consumed per day
        loot_carried: Amount of loot carried
        noncombatant_count: Number of noncombatants
        noncombatant_percentage: Percentage of noncombatants
        status: Current status (idle/marching/besieging/etc)
        forced_march_weeks: Weeks of forced marching
        days_without_supplies: Days without adequate supplies
        days_marched_this_week: Days marched this week (enforces caps)
        status_effects: JSON object with status effects
        column_length_miles: Length of army column in miles
        rest_duration_days: Duration of rest period
        rest_started_day: Game day when rest started
        rest_location_stronghold_id: Stronghold where resting (if applicable)
    """

    __tablename__ = "armies"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)
    current_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    destination_hex_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hexes.id"), nullable=True
    )
    rest_location_stronghold_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("strongholds.id"), nullable=True
    )

    # Army attributes
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    movement_points_remaining: Mapped[float] = mapped_column(nullable=False, default=0.0)
    morale_current: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    morale_resting: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    morale_max: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    supplies_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplies_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_consumption: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loot_carried: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    noncombatant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    noncombatant_percentage: Mapped[float] = mapped_column(nullable=False, default=0.25)
    status: Mapped[str] = mapped_column(String, nullable=False)
    forced_march_weeks: Mapped[float] = mapped_column(nullable=False, default=0.0)
    days_without_supplies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_marched_this_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_effects: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    column_length_miles: Mapped[float] = mapped_column(nullable=False, default=0.0)
    rest_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rest_started_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="armies")
    commander: Mapped["Commander"] = relationship("Commander", back_populates="armies")
    current_hex: Mapped["Hex"] = relationship(
        "Hex",
        back_populates="armies",
        foreign_keys=[current_hex_id],
    )
    destination_hex: Mapped[Optional["Hex"]] = relationship(
        "Hex", foreign_keys=[destination_hex_id]
    )
    rest_location: Mapped[Optional["Stronghold"]] = relationship("Stronghold")
    detachments: Mapped[list["Detachment"]] = relationship(
        "Detachment", back_populates="army", cascade="all, delete-orphan"
    )
    movement_legs: Mapped[list["MovementLeg"]] = relationship(
        "MovementLeg", back_populates="army", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="army")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('idle', 'marching', 'forced_march', 'night_march', 'resting', "
            "'foraging', 'besieging', 'in_battle', 'routed', 'garrisoned')",
            name="ck_armies_status",
        ),
        Index("idx_armies_commander", "commander_id"),
        Index("idx_armies_hex", "current_hex_id"),
        Index("idx_armies_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Army(id={self.id}, commander={self.commander_id}, status='{self.status}')>"

    # Compatibility with ARCHITECTURE.md naming while keeping schema stable
    @property
    def daily_supply_consumption(self) -> int:
        """Alias for `daily_consumption` to match documentation terminology."""
        return int(self.daily_consumption)

    @daily_supply_consumption.setter
    def daily_supply_consumption(self, value: int) -> None:
        self.daily_consumption = int(value)

    @property
    def is_undersupplied(self) -> bool:
        """Derived flag per rules: insufficient supplies at start of day.

        True if `supplies_current < daily_consumption` or `days_without_supplies > 0`.
        """
        return (self.supplies_current < self.daily_consumption) or (self.days_without_supplies > 0)


class UnitType(Base, TimestampCreatedMixin):
    """Represents a type of military unit.

    This is a catalog table that defines all available unit types in the game.
    Unit types have different combat strengths, supply costs, and special abilities.

    Attributes:
        id: Primary key
        name: Unique name of the unit type
        category: Category of unit (infantry/cavalry/special/siege)
        battle_multiplier: Combat multiplier (e.g., heavy cavalry = 4.0)
        supply_cost_per_day: Daily supply consumption
        can_travel_offroad: Whether unit can travel off-road
        special_abilities: JSON object with special abilities
        content_pack: Content pack this unit type belongs to (NULL for base game)
    """

    __tablename__ = "unit_types"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Unit type attributes
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    battle_multiplier: Mapped[float] = mapped_column(nullable=False, default=1.0)
    supply_cost_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    can_travel_offroad: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    special_abilities: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    content_pack: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    detachments: Mapped[list["Detachment"]] = relationship("Detachment", back_populates="unit_type")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "category IN ('infantry', 'cavalry', 'special', 'siege')",
            name="ck_unit_types_category",
        ),
        Index("idx_unit_types_content_pack", "content_pack"),
    )

    def __repr__(self) -> str:
        return f"<UnitType(id={self.id}, name='{self.name}', category='{self.category}')>"


class Detachment(Base, TimestampCreatedMixin):
    """Represents a detachment (military unit) within an army.

    A detachment is a specific group of soldiers of a particular unit type.
    It can have wagons, siege engines, and special instance data.

    Attributes:
        id: Primary key
        army_id: Foreign key to army
        unit_type_id: Foreign key to unit type
        name: Name of the detachment
        soldier_count: Number of soldiers (0 for siege_engines)
        wagon_count: Number of wagons
        engine_count: Number of siege engines (for siege_engines unit type)
        region_of_origin: Region where this detachment was recruited
        formation_position: Position in army formation
        honors: JSON array of earned honors/titles
        instance_data: JSON for unit-specific state
    """

    __tablename__ = "detachments"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    army_id: Mapped[int] = mapped_column(Integer, ForeignKey("armies.id"), nullable=False)
    unit_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("unit_types.id"), nullable=False)

    # Detachment attributes
    name: Mapped[str] = mapped_column(String, nullable=False)
    soldier_count: Mapped[int] = mapped_column(Integer, nullable=False)
    wagon_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engine_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of siege engines (must be multiple of 10, or None for non-siege units)",
    )
    region_of_origin: Mapped[str | None] = mapped_column(String, nullable=True)
    formation_position: Mapped[int] = mapped_column(Integer, nullable=False)
    honors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    instance_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    army: Mapped["Army"] = relationship("Army", back_populates="detachments")
    unit_type: Mapped["UnitType"] = relationship("UnitType", back_populates="detachments")

    # Table constraints
    __table_args__ = (
        Index("idx_detachments_army", "army_id"),
        Index("idx_detachments_unit_type", "unit_type_id"),
    )

    @validates("engine_count")
    def validate_engine_count(self, key: str, value: int | None) -> int | None:  # noqa: ARG002
        """Validate that engine_count is a multiple of 10.

        From RULES_IMPLEMENTATION_NOTES.md:
        Siege engines come in groups of 10. This reflects the logistical
        unit size for siege equipment.

        Args:
            key: Field name (unused, required by SQLAlchemy)
            value: Engine count to validate

        Returns:
            Validated engine count

        Raises:
            ValueError: If engine_count is not a multiple of 10
        """
        if value is not None and value % 10 != 0:
            raise ValueError(
                f"Siege engine count must be a multiple of 10, got {value}. "
                "Engines are organized in groups of 10."
            )
        return value

    def __repr__(self) -> str:
        return f"<Detachment(id={self.id}, name='{self.name}', soldiers={self.soldier_count})>"


class MovementLeg(Base, TimestampCreatedMixin):
    """Represents a single leg of an army's movement itinerary.

    Movement legs break down a movement order into individual hex-to-hex
    segments, allowing for mid-daypart interruptions and tracking.

    Attributes:
        id: Primary key
        army_id: Foreign key to army
        order_id: Foreign key to order
        seq: Sequence number of this leg (0, 1, 2, ...)
        from_hex_id: Source hex
        to_hex_id: Destination hex
        road: Whether this leg uses a road
        distance_miles: Distance in miles
        base_travel_time_hours: Base travel time in hours (before modifiers)
        planned_start_day: Planned start game day
        planned_start_part: Planned start daypart
        planned_end_day: Planned end game day
        planned_end_part: Planned end daypart
        actual_end_day: Actual end game day (when completed)
        actual_end_part: Actual end daypart (when completed)
        status: Status of this leg (pending/in_progress/completed/interrupted/cancelled)
        interruption_reason: Reason for interruption (if applicable)
    """

    __tablename__ = "movement_legs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    army_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("armies.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    from_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    to_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)

    # Movement leg attributes
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    road: Mapped[bool] = mapped_column(Boolean, nullable=False)
    distance_miles: Mapped[float] = mapped_column(nullable=False)
    base_travel_time_hours: Mapped[float] = mapped_column(nullable=False)
    planned_start_day: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start_part: Mapped[str] = mapped_column(String, nullable=False)
    planned_end_day: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_end_part: Mapped[str] = mapped_column(String, nullable=False)
    actual_end_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_end_part: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    interruption_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    army: Mapped["Army"] = relationship("Army", back_populates="movement_legs")
    order: Mapped["Order"] = relationship("Order")
    from_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[from_hex_id])
    to_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[to_hex_id])

    # Table constraints
    __table_args__ = (
        UniqueConstraint("army_id", "order_id", "seq", name="uq_movement_legs"),
        CheckConstraint(
            "planned_start_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_movement_legs_planned_start_part",
        ),
        CheckConstraint(
            "planned_end_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_movement_legs_planned_end_part",
        ),
        CheckConstraint(
            "actual_end_part IS NULL OR actual_end_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_movement_legs_actual_end_part",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'interrupted', 'cancelled')",
            name="ck_movement_legs_status",
        ),
        Index("idx_movement_legs_army", "army_id"),
        Index("idx_movement_legs_order", "order_id"),
        Index("idx_movement_legs_edge", "from_hex_id", "to_hex_id"),
        Index("idx_movement_legs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MovementLeg(id={self.id}, army={self.army_id}, seq={self.seq}, status='{self.status}')>"
