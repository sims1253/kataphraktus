"""Dataclasses describing every Cataphract game entity.

The current ORM layer includes a large number of tables with significant
boilerplate.  The dataclasses below provide a concise, in-memory
representation for the same concepts so the rules layer can operate without
touching the database directly.

Persistence adapters can translate between these dataclasses and the
underlying storage (SQLAlchemy or otherwise).  Within the new domain layer
we only interact with these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import NewType

from .enums import (
    ArmyStatus,
    DayPart,
    NavalStatus,
    OperationOutcome,
    OperationType,
    OrderStatus,
    RelationType,
    Season,
    SiegeStatus,
    StrongholdType,
)

# --- Strongly typed identifiers -------------------------------------------------

CampaignID = NewType("CampaignID", int)
HexID = NewType("HexID", int)
FactionID = NewType("FactionID", int)
StrongholdID = NewType("StrongholdID", int)
CommanderID = NewType("CommanderID", int)
PlayerID = NewType("PlayerID", int)
ArmyID = NewType("ArmyID", int)
DetachmentID = NewType("DetachmentID", int)
UnitTypeID = NewType("UnitTypeID", int)
MovementLegID = NewType("MovementLegID", int)
MessageID = NewType("MessageID", int)
OrderID = NewType("OrderID", int)
EventID = NewType("EventID", int)
SiegeID = NewType("SiegeID", int)
BattleID = NewType("BattleID", int)
WeatherID = NewType("WeatherID", int)
ShipTypeID = NewType("ShipTypeID", int)
ShipID = NewType("ShipID", int)
MercenaryCompanyID = NewType("MercenaryCompanyID", int)
MercenaryContractID = NewType("MercenaryContractID", int)
OperationID = NewType("OperationID", int)
MessageLegID = NewType("MessageLegID", int)


# --- Core dataclasses -----------------------------------------------------------


@dataclass(slots=True)
class Trait:
    """Commander trait definition (catalog entry)."""

    id: int
    name: str
    description: str
    scope_tags: list[str]
    effect_data: dict[str, object]
    ruleset_version: str = "1.1"
    content_pack: str | None = None


@dataclass(slots=True)
class Commander:
    """Commander participating in a campaign."""

    id: CommanderID
    campaign_id: CampaignID
    name: str
    faction_id: FactionID
    age: int
    traits: list[Trait] = field(default_factory=list)
    player_id: PlayerID | None = None
    related_to_id: CommanderID | None = None
    relationship_type: str | None = None
    current_hex_id: HexID | None = None
    status: str = "active"
    captured_by_faction_id: FactionID | None = None


@dataclass(slots=True)
class FactionRelation:
    """Relationship between two factions."""

    other_faction_id: FactionID
    relation_type: RelationType
    since_day: int


@dataclass(slots=True)
class Faction:
    """Faction controlling territory and commanders."""

    id: FactionID
    campaign_id: CampaignID
    name: str
    color: str
    description: str | None = None
    special_rules: dict[str, object] | None = None
    unique_units: list[str] | None = None
    relations: dict[FactionID, FactionRelation] = field(default_factory=dict)


@dataclass(slots=True)
class Hex:
    """Map hex tile."""

    id: HexID
    campaign_id: CampaignID
    q: int
    r: int
    terrain: str
    settlement: int
    is_good_country: bool = False
    has_road: bool = False
    river_sides: list[str] | None = None
    foraging_times_remaining: int = 5
    is_torched: bool = False
    last_foraged_day: int | None = None
    last_recruited_day: int | None = None
    last_torched_day: int | None = None
    last_control_change_day: int | None = None
    controlling_faction_id: FactionID | None = None


@dataclass(slots=True)
class RoadEdge:
    """Road graph edge between two hexes."""

    from_hex_id: HexID
    to_hex_id: HexID
    quality: str
    base_cost_hours: float
    status: str = "open"
    seasonal_modifiers: dict[str, float] | None = None
    damaged_since_day: int | None = None


@dataclass(slots=True)
class RiverCrossing:
    """Bridge or ford connecting two hexes."""

    from_hex_id: HexID
    to_hex_id: HexID
    crossing_type: str  # bridge | ford | none
    status: str = "open"
    ford_quality: str | None = None
    seasonal_closures: dict[str, bool] | None = None


@dataclass(slots=True)
class Stronghold:
    """Stronghold located in a hex."""

    id: StrongholdID
    campaign_id: CampaignID
    hex_id: HexID
    type: StrongholdType
    controlling_faction_id: FactionID
    defensive_bonus: int
    threshold: int
    current_threshold: int
    gates_open: bool = False
    garrison_army_id: ArmyID | None = None
    supplies_held: int = 0
    loot_held: int = 0


@dataclass(slots=True)
class UnitType:
    """Catalog entry describing a detachment type."""

    id: UnitTypeID
    name: str
    category: str
    battle_multiplier: float
    supply_cost_per_day: int
    can_travel_offroad: bool
    special_abilities: dict[str, object] | None = None
    content_pack: str | None = None


@dataclass(slots=True)
class Detachment:
    """Detachment belonging to an army."""

    id: DetachmentID
    unit_type_id: UnitTypeID
    soldiers: int
    wagons: int = 0
    engines: int = 0
    name: str | None = None
    region_of_origin: str | None = None
    honors: list[str] | None = None
    instance_data: dict[str, object] | None = None


@dataclass(slots=True)
class Army:
    """Army consisting of detachments and supplies."""

    id: ArmyID
    campaign_id: CampaignID
    commander_id: CommanderID
    current_hex_id: HexID
    detachments: list[Detachment]
    status: ArmyStatus
    movement_points_remaining: float = 0.0
    morale_current: int = 9
    morale_resting: int = 9
    morale_max: int = 12
    supplies_current: int = 0
    supplies_capacity: int = 0
    daily_supply_consumption: int = 0
    loot_carried: int = 0
    noncombatant_count: int = 0
    noncombatant_percentage: float = 0.25
    forced_march_days: float = 0.0
    days_without_supplies: int = 0
    days_marched_this_week: int = 0
    status_effects: dict[str, object] | None = None
    column_length_miles: float = 0.0
    rest_duration_days: int | None = None
    rest_started_day: int | None = None
    destination_hex_id: HexID | None = None
    rest_location_stronghold_id: StrongholdID | None = None
    embarked_ship_id: ShipID | None = None
    is_blockaded: bool = False
    orders_queue: list[OrderID] = field(default_factory=list)
    last_battle_day: int | None = None
    last_retreat_day: int | None = None


@dataclass(slots=True)
class ShipType:
    """Catalog of ship types."""

    id: ShipTypeID
    name: str
    capacity_soldiers: int
    capacity_cavalry: int
    capacity_supplies: int
    daily_cost_loot: int
    can_sea: bool
    can_river: bool
    special_rules: dict[str, object] | None = None
    content_pack: str | None = None


@dataclass(slots=True)
class Ship:
    """Individual ship."""

    id: ShipID
    campaign_id: CampaignID
    controlling_faction_id: FactionID
    current_hex_id: HexID
    ship_type_id: ShipTypeID
    status: NavalStatus
    morale: int = 9
    has_siege_equipment: bool = False
    return_day: int | None = None
    embarked_army_id: ArmyID | None = None
    movement_points_remaining: float = 0.0
    current_route: list[HexID] = field(default_factory=list)
    travel_days_remaining: float = 0.0


@dataclass(slots=True)
class MercenaryCompany:
    """Catalog of hireable mercenary forces."""

    id: MercenaryCompanyID
    name: str
    description: str
    base_rates: dict[str, int]
    default_composition: list[dict[str, object]]
    available: bool = True


@dataclass(slots=True)
class MercenaryContract:
    """Active mercenary hire."""

    id: MercenaryContractID
    company_id: MercenaryCompanyID
    commander_id: CommanderID
    army_id: ArmyID | None
    start_day: int
    end_day: int | None
    status: str
    last_upkeep_day: int
    negotiated_rates: dict[str, int] | None = None
    days_unpaid: int = 0


@dataclass(slots=True)
class Order:
    """Order issued to an army or commander."""

    id: OrderID
    campaign_id: CampaignID
    army_id: ArmyID | None
    commander_id: CommanderID
    order_type: str
    parameters: dict[str, object]
    issued_at: datetime
    execute_at: datetime
    execute_day: int | None = None
    execute_part: DayPart | None = None
    status: OrderStatus = OrderStatus.PENDING
    result: dict[str, object] | None = None
    priority: int = 0


@dataclass(slots=True)
class MovementLeg:
    """Single leg of a planned movement path."""

    id: MovementLegID
    from_hex_id: HexID
    to_hex_id: HexID
    distance_miles: float
    on_road: bool
    has_river_ford: bool = False
    is_night: bool = False
    has_fork: bool = False
    alternate_hex_id: HexID | None = None


@dataclass(slots=True)
class MessageLeg:
    """Represents a leg of messenger travel for auditing delays."""

    id: MessageLegID
    from_hex_id: HexID
    to_hex_id: HexID
    distance_miles: float
    travel_time_days: float
    terrain: str


@dataclass(slots=True)
class Message:
    """Communication between commanders."""

    id: MessageID
    campaign_id: CampaignID
    sender_id: CommanderID
    recipient_id: CommanderID
    content: str
    sent_at: datetime
    delivered_at: datetime | None
    travel_time_days: float
    territory_type: str
    status: str
    legs: list[MessageLeg] = field(default_factory=list)
    days_remaining: float = 0.0
    failure_reason: str | None = None


@dataclass(slots=True)
class Operation:
    """Espionage/special operation."""

    id: OperationID
    commander_id: CommanderID
    operation_type: OperationType
    target_descriptor: dict[str, object]
    loot_cost: int
    complexity: str
    success_chance: float
    executed_on_day: int | None = None
    outcome: OperationOutcome = OperationOutcome.PENDING
    result: dict[str, object] | None = None
    territory_type: str | None = None
    difficulty_modifier: int = 0


@dataclass(slots=True)
class Siege:
    """Ongoing siege record."""

    id: SiegeID
    stronghold_id: StrongholdID
    attacker_army_ids: list[ArmyID]
    defender_army_id: ArmyID | None
    started_on_day: int
    weeks_elapsed: int
    current_threshold: int
    threshold_modifiers: list[dict[str, object]]
    siege_engines_count: int
    attempts: list[dict[str, object]]
    status: SiegeStatus = SiegeStatus.ONGOING


@dataclass(slots=True)
class RecruitmentProject:
    """Pending army recruitment effort."""

    id: int
    stronghold_id: StrongholdID
    faction_id: FactionID
    commander_id: CommanderID
    rally_hex_id: HexID
    started_on_day: int
    completes_on_day: int
    infantry: int
    cavalry: int
    wagons: int
    noncombatants: int
    source_hex_ids: list[HexID]
    pending_order_id: OrderID
    revolt_triggered: bool = False


@dataclass(slots=True)
class Battle:
    """Battle resolution record."""

    id: BattleID
    campaign_id: CampaignID
    game_day: int
    hex_id: HexID
    attacker_army_ids: list[ArmyID]
    defender_army_ids: list[ArmyID]
    attacker_rolls: dict[ArmyID, int]
    defender_rolls: dict[ArmyID, int]
    victor_side: str
    roll_difference: int
    casualties: dict[ArmyID, float]
    morale_changes: dict[ArmyID, int]
    commanders_captured: list[CommanderID]
    loot_captured: int
    routes: list[ArmyID]


@dataclass(slots=True)
class Weather:
    """Weather record for a campaign day."""

    id: WeatherID
    campaign_id: CampaignID
    game_day: int
    description: str
    severity: str


@dataclass(slots=True)
class Event:
    """Event log entry."""

    id: EventID
    campaign_id: CampaignID
    game_day: int
    timestamp: datetime
    event_type: str
    involved_entities: dict[str, list[int]]
    description: str
    details: dict[str, object] | None = None
    visible_to: list[CommanderID] | None = None
    referee_notes: str | None = None


@dataclass(slots=True)
class CampaignMap:
    """Aggregated map state (hex grid + connectivity)."""

    hexes: dict[HexID, Hex] = field(default_factory=dict)
    roads: list[RoadEdge] = field(default_factory=list)
    river_crossings: list[RiverCrossing] = field(default_factory=list)


@dataclass(slots=True)
class Campaign:
    """Root aggregate representing an entire campaign."""

    id: CampaignID
    name: str
    start_date: date
    current_day: int
    current_part: DayPart
    season: Season
    status: str
    map: CampaignMap = field(default_factory=CampaignMap)
    factions: dict[FactionID, Faction] = field(default_factory=dict)
    commanders: dict[CommanderID, Commander] = field(default_factory=dict)
    armies: dict[ArmyID, Army] = field(default_factory=dict)
    strongholds: dict[StrongholdID, Stronghold] = field(default_factory=dict)
    ships: dict[ShipID, Ship] = field(default_factory=dict)
    unit_types: dict[UnitTypeID, UnitType] = field(default_factory=dict)
    sieges: dict[SiegeID, Siege] = field(default_factory=dict)
    battles: dict[BattleID, Battle] = field(default_factory=dict)
    mercenary_companies: dict[MercenaryCompanyID, MercenaryCompany] = field(default_factory=dict)
    mercenary_contracts: dict[MercenaryContractID, MercenaryContract] = field(default_factory=dict)
    operations: dict[OperationID, Operation] = field(default_factory=dict)
    orders: dict[OrderID, Order] = field(default_factory=dict)
    messages: dict[MessageID, Message] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    weather: dict[int, Weather] = field(default_factory=dict)
    recruitments: dict[int, RecruitmentProject] = field(default_factory=dict)
