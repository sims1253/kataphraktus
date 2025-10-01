"""Map-related models for the Cataphract game system.

This module contains all models related to the hex map, including:
- Hexes (terrain and territory)
- Road edges (road graph system)
- River crossings (bridges, fords, and hazards)
- Crossing queues (bridge capacity management)
- Map features (special hex/edge/stronghold effects)
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .army import Army
    from .faction import Faction
    from .game import Game
    from .stronghold import Stronghold


class Hex(Base):
    """Represents a single hex on the game map.

    Each hex has terrain, settlement score, and tracks various game state
    including foraging capacity, territory control, and hex economy for
    revolt rules.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        q: Axial coordinate q
        r: Axial coordinate r
        terrain_type: Type of terrain (flatland/hills/forest/mountain/water/coast)
        is_good_country: Whether this is good country (better foraging)
        has_road: Denormalized UI flag (road_edges is source of truth)
        settlement_score: Economic value (0/20/40/60/80/100)
        river_sides: JSON array of hex edges with rivers (e.g., ["NE", "E"])
        foraging_times_remaining: How many more times hex can be foraged
        is_torched: Whether hex has been torched
        last_foraged_day: Game day when last foraged (for revolt rules)
        last_recruited_day: Game day when last recruited (for revolt rules)
        last_torched_day: Game day when last torched (for revolt rules)
        controlling_faction_id: Faction that controls this hex (NULL if unclaimed)
        last_control_change_day: Game day when control last changed
    """

    __tablename__ = "hexes"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    controlling_faction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    # Axial coordinates
    q: Mapped[int] = mapped_column(Integer, nullable=False)
    r: Mapped[int] = mapped_column(Integer, nullable=False)

    # Terrain and features
    terrain_type: Mapped[str] = mapped_column(String, nullable=False)
    is_good_country: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_road: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settlement_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    river_sides: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Foraging and torching
    foraging_times_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_torched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Hex economy tracking for revolt rules
    last_foraged_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_recruited_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_torched_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Territory control
    last_control_change_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="hexes")
    controlling_faction: Mapped[Optional["Faction"]] = relationship(
        "Faction", back_populates="controlled_hexes"
    )
    strongholds: Mapped[list["Stronghold"]] = relationship("Stronghold", back_populates="hex")
    armies: Mapped[list["Army"]] = relationship(
        "Army",
        back_populates="current_hex",
        foreign_keys="Army.current_hex_id",
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint("game_id", "q", "r", name="uq_hexes_game_coords"),
        CheckConstraint(
            "terrain_type IN ('flatland', 'hills', 'forest', 'mountain', 'water', 'coast')",
            name="ck_hexes_terrain_type",
        ),
        CheckConstraint(
            "settlement_score IS NULL OR settlement_score IN (0, 20, 40, 60, 80, 100)",
            name="ck_hexes_settlement_score",
        ),
        Index("idx_hexes_game", "game_id"),
        Index("idx_hexes_coords", "game_id", "q", "r"),
        Index("idx_hexes_control", "controlling_faction_id"),
    )

    def __repr__(self) -> str:
        return f"<Hex(id={self.id}, q={self.q}, r={self.r}, terrain='{self.terrain_type}')>"


class RoadEdge(Base, TimestampCreatedMixin):
    """Represents a road connection between two hexes.

    The road graph system uses explicit edges to model roads, allowing
    for different road qualities, seasonal modifiers, and road status.

    Canonical Ordering:
        Road edges are stored in canonical form with from_hex_id < to_hex_id.
        This ensures each edge exists only once in the database, preventing
        duplicates and simplifying pathfinding queries.

    Example:
        Edge between hex 5 and hex 10 is always stored as (5, 10), never (10, 5).

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        from_hex_id: Source hex (always smaller ID)
        to_hex_id: Destination hex (always larger ID)
        road_quality: Quality of road (major/minor/trail)
        base_cost_hours: Base movement time in hours
        seasonal_modifiers: JSON with seasonal multipliers (e.g., {"winter": 2.0})
        status: Road status (open/closed/damaged)
        damaged_since_day: Game day when road was damaged (if applicable)
    """

    __tablename__ = "road_edges"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    from_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    to_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)

    # Road attributes
    road_quality: Mapped[str] = mapped_column(String, nullable=False)
    base_cost_hours: Mapped[float] = mapped_column(nullable=False)
    seasonal_modifiers: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    damaged_since_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    from_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[from_hex_id])
    to_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[to_hex_id])

    # Table constraints
    __table_args__ = (
        CheckConstraint("from_hex_id < to_hex_id", name="ck_road_edges_order"),
        UniqueConstraint("game_id", "from_hex_id", "to_hex_id", name="uq_road_edges_hexes"),
        CheckConstraint(
            "road_quality IN ('major', 'minor', 'trail')",
            name="ck_road_edges_quality",
        ),
        CheckConstraint("status IN ('open', 'closed', 'damaged')", name="ck_road_edges_status"),
        Index("idx_road_edges_from", "from_hex_id"),
        Index("idx_road_edges_to", "to_hex_id"),
        Index("idx_road_edges_status", "status"),
    )

    @staticmethod
    def normalize_edge(hex_a_id: int, hex_b_id: int) -> tuple[int, int]:
        """Normalize edge to canonical form (smaller_id, larger_id).

        Args:
            hex_a_id: First hex ID
            hex_b_id: Second hex ID

        Returns:
            Tuple (from_hex_id, to_hex_id) where from_hex_id < to_hex_id

        Example:
            >>> RoadEdge.normalize_edge(10, 5)
            (5, 10)
            >>> RoadEdge.normalize_edge(3, 7)
            (3, 7)
        """
        return (min(hex_a_id, hex_b_id), max(hex_a_id, hex_b_id))

    def __repr__(self) -> str:
        return f"<RoadEdge(id={self.id}, from={self.from_hex_id}, to={self.to_hex_id}, quality='{self.road_quality}')>"


class RiverCrossing(Base, TimestampCreatedMixin):
    """Represents a river crossing between two hexes.

    River crossings can be bridges, fords, or impassable. They have
    capacity limits, seasonal closures, and special hazard rules.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        from_hex_id: Lower hex ID (for canonical ordering)
        to_hex_id: Higher hex ID (for canonical ordering)
        side: Legacy side field (NE/E/SE/SW/W/NW from from_hex perspective)
        crossing_type: Type of crossing (bridge/ford/none)
        bridge_capacity: Max column-miles per daypart if bridge
        ford_quality: Ford difficulty (easy/difficult/impassable)
        status: Crossing status (open/closed/destroyed)
        seasonal_closures: JSON with seasonal closures (e.g., {"spring": true})
        hazard_rules: JSON with special hazard rules
        destroyed_on_day: Game day when crossing was destroyed
    """

    __tablename__ = "river_crossings"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    from_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    to_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)

    # Legacy side field
    side: Mapped[str | None] = mapped_column(String, nullable=True)

    # Crossing attributes
    crossing_type: Mapped[str] = mapped_column(String, nullable=False)
    bridge_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ford_quality: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    seasonal_closures: Mapped[dict[str, bool] | None] = mapped_column(JSON, nullable=True)
    hazard_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    destroyed_on_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    from_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[from_hex_id])
    to_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[to_hex_id])

    # Table constraints
    __table_args__ = (
        UniqueConstraint("game_id", "from_hex_id", "to_hex_id", name="uq_river_crossings"),
        CheckConstraint("from_hex_id < to_hex_id", name="ck_river_crossings_order"),
        CheckConstraint(
            "side IS NULL OR side IN ('NE', 'E', 'SE', 'SW', 'W', 'NW')",
            name="ck_river_crossings_side",
        ),
        CheckConstraint(
            "crossing_type IN ('bridge', 'ford', 'none')",
            name="ck_river_crossings_type",
        ),
        CheckConstraint(
            "ford_quality IS NULL OR ford_quality IN ('easy', 'difficult', 'impassable')",
            name="ck_river_crossings_ford_quality",
        ),
        CheckConstraint(
            "status IN ('open', 'closed', 'destroyed')",
            name="ck_river_crossings_status",
        ),
        Index("idx_river_crossings_edge", "from_hex_id", "to_hex_id"),
        Index("idx_river_crossings_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RiverCrossing(id={self.id}, from={self.from_hex_id}, to={self.to_hex_id}, type='{self.crossing_type}')>"


class CrossingQueue(Base, TimestampCreatedMixin):
    """Manages bridge capacity and queuing for river crossings.

    When multiple armies attempt to cross a bridge, this table tracks
    their position in the queue and crossing progress.

    Attributes:
        id: Primary key
        crossing_id: Foreign key to river_crossings
        army_id: Foreign key to armies
        pending_miles: Length of column not yet crossed
        enqueued_day: Game day when army joined queue
        enqueued_part: Daypart when army joined queue
        crossing_start_day: Game day when crossing began
        crossing_start_part: Daypart when crossing began
        expected_completion_day: Game day when crossing should complete
        expected_completion_part: Daypart when crossing should complete
        status: Queue status (waiting/crossing/completed/interrupted)
    """

    __tablename__ = "crossing_queues"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    crossing_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("river_crossings.id", ondelete="CASCADE"),
        nullable=False,
    )
    army_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("armies.id", ondelete="CASCADE"), nullable=False
    )

    # Queue state
    pending_miles: Mapped[float] = mapped_column(nullable=False)
    enqueued_day: Mapped[int] = mapped_column(Integer, nullable=False)
    enqueued_part: Mapped[str] = mapped_column(String, nullable=False)
    crossing_start_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crossing_start_part: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_completion_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_completion_part: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="waiting")

    # Relationships
    crossing: Mapped["RiverCrossing"] = relationship("RiverCrossing")
    army: Mapped["Army"] = relationship("Army")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("crossing_id", "army_id", name="uq_crossing_queues"),
        CheckConstraint(
            "enqueued_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_crossing_queues_enqueued_part",
        ),
        CheckConstraint(
            "crossing_start_part IS NULL OR crossing_start_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_crossing_queues_start_part",
        ),
        CheckConstraint(
            "expected_completion_part IS NULL OR expected_completion_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_crossing_queues_completion_part",
        ),
        CheckConstraint(
            "status IN ('waiting', 'crossing', 'completed', 'interrupted')",
            name="ck_crossing_queues_status",
        ),
        Index("idx_crossing_queues_crossing", "crossing_id"),
        Index("idx_crossing_queues_army", "army_id"),
        Index("idx_crossing_queues_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<CrossingQueue(id={self.id}, crossing={self.crossing_id}, army={self.army_id}, status='{self.status}')>"


class MapFeature(Base, TimestampCreatedMixin):
    """Represents special features and hazards on the map.

    Map features can be attached to hexes, edges, or strongholds and
    provide structured effects through JSON effect_data.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        scope: Where this feature applies (hex/edge/stronghold)
        hex_id: Foreign key to hex (if scope='hex')
        from_hex_id: Foreign key to source hex (if scope='edge')
        to_hex_id: Foreign key to destination hex (if scope='edge')
        stronghold_id: Foreign key to stronghold (if scope='stronghold')
        name: Name of the feature
        description: Description of the feature
        effect_data: JSON with structured effect hooks
        content_pack: Content pack this feature belongs to (NULL for base game)
    """

    __tablename__ = "map_features"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    hex_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=True)
    from_hex_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=True)
    to_hex_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=True)
    stronghold_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("strongholds.id"), nullable=True
    )

    # Feature attributes
    scope: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    effect_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_pack: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    hex: Mapped[Optional["Hex"]] = relationship("Hex", foreign_keys=[hex_id])
    from_hex: Mapped[Optional["Hex"]] = relationship("Hex", foreign_keys=[from_hex_id])
    to_hex: Mapped[Optional["Hex"]] = relationship("Hex", foreign_keys=[to_hex_id])
    stronghold: Mapped[Optional["Stronghold"]] = relationship("Stronghold")

    # Table constraints
    __table_args__ = (
        CheckConstraint("scope IN ('hex', 'edge', 'stronghold')", name="ck_map_features_scope"),
        Index("idx_map_features_scope", "scope"),
        Index("idx_map_features_hex", "hex_id"),
        Index("idx_map_features_edge", "from_hex_id", "to_hex_id"),
        Index("idx_map_features_stronghold", "stronghold_id"),
    )

    def __repr__(self) -> str:
        return f"<MapFeature(id={self.id}, name='{self.name}', scope='{self.scope}')>"
