"""Army recruitment rules for Cataphract campaigns."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain import supply
from cataphract.domain.enums import ArmyStatus, StrongholdType
from cataphract.domain.models import (
    Army,
    Commander,
    CommanderID,
    Detachment,
    DetachmentID,
    Faction,
    FactionID,
    Hex,
    HexID,
    OrderID,
    RecruitmentProject,
    Stronghold,
    UnitType,
    UnitTypeID,
)
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.hex_math import HexCoord, hex_distance
from cataphract.utils.rng import roll_dice


@dataclass(slots=True)
class RecruitmentInput:
    """Parameters required to kick off a recruitment."""

    stronghold: Stronghold
    commander: Commander
    rally_hex: Hex
    pending_order_id: OrderID


@dataclass(slots=True)
class RecruitmentResult:
    """Returned when a recruitment project is initiated."""

    project: RecruitmentProject
    revolts: list[Army]
    detail: str


@dataclass(slots=True)
class RecruitmentCompletionOptions:
    """Parameters controlling recruitment completion."""

    army_name: str
    infantry_type: UnitType
    cavalry_type: UnitType | None = None
    rules: RulesConfig = DEFAULT_RULES


@dataclass(slots=True)
class RecruitmentCompletion:
    """Returned when a recruitment project completes."""

    army: Army
    detail: str


def start_recruitment(
    campaign,
    data: RecruitmentInput,
    *,
    rules: RulesConfig = DEFAULT_RULES,
) -> RecruitmentResult:
    """Create a recruitment project and apply any revolt consequences."""

    eligible_hexes = _eligible_hexes(campaign, data.stronghold)
    if not eligible_hexes:
        raise ValueError("no eligible hexes for recruitment")

    infantry_raw = sum(_hex_settlement(campaign, hex_id) for hex_id in eligible_hexes)
    if infantry_raw <= 0:
        raise ValueError("recruitment area has zero settlement")

    cavalry_raw = 0.0
    wagon_raw = 0.0
    for hex_id in eligible_hexes:
        hex_tile = campaign.map.hexes[hex_id]
        if hex_tile.is_good_country:
            cavalry_raw += hex_tile.settlement * 0.25
            wagon_raw += hex_tile.settlement * 0.05

    infantry_total = _round_to_nearest_hundred(infantry_raw)
    if infantry_total <= 0:
        raise ValueError("recruitment yielded too few infantry")

    scale = infantry_total / infantry_raw
    cavalry_total = round(cavalry_raw * scale) if cavalry_raw > 0 else 0
    wagon_total = round(wagon_raw * scale) if wagon_raw > 0 else 0
    noncombatants = int(infantry_total * rules.supply.base_noncombatant_ratio)

    revolts: list[Army] = []
    revolt_triggered = False
    for hex_id in eligible_hexes:
        hex_tile = campaign.map.hexes[hex_id]
        if _should_revolt(campaign, hex_tile, rules):
            revolt_triggered = True
            revolts.append(_spawn_revolt(campaign, hex_tile, rules))
        hex_tile.last_recruited_day = campaign.current_day

    project_id = _next_project_id(campaign)
    completes_on_day = campaign.current_day + rules.recruitment.muster_duration_days
    project = RecruitmentProject(
        id=project_id,
        stronghold_id=data.stronghold.id,
        faction_id=data.commander.faction_id,
        commander_id=data.commander.id,
        rally_hex_id=data.rally_hex.id,
        started_on_day=campaign.current_day,
        completes_on_day=completes_on_day,
        infantry=infantry_total,
        cavalry=cavalry_total,
        wagons=wagon_total,
        noncombatants=noncombatants,
        source_hex_ids=list(eligible_hexes),
        pending_order_id=data.pending_order_id,
        revolt_triggered=revolt_triggered,
    )
    campaign.recruitments[project.id] = project

    detail = (
        f"recruitment underway; infantry={infantry_total}, cavalry={cavalry_total}, "
        f"wagons={wagon_total}, completes day {completes_on_day}"
    )
    return RecruitmentResult(project=project, revolts=revolts, detail=detail)


def complete_recruitment(
    campaign,
    project: RecruitmentProject,
    options: RecruitmentCompletionOptions,
) -> RecruitmentCompletion:
    """Resolve recruitment completion and create the new army."""

    commander = campaign.commanders.get(project.commander_id)
    if commander is None:
        raise ValueError("assigned commander not found")

    rally_hex = campaign.map.hexes.get(project.rally_hex_id)
    if rally_hex is None:
        raise ValueError("rally hex not found")

    army_id = _next_army_id(campaign)
    detachment_id = _next_detachment_id(campaign)

    infantry_det = Detachment(
        id=detachment_id,
        unit_type_id=options.infantry_type.id,
        soldiers=project.infantry,
        wagons=project.wagons,
        name=f"{options.army_name} Infantry",
    )

    detachments = [infantry_det]

    if project.cavalry > 0 and options.cavalry_type is not None:
        cav_det = Detachment(
            id=_next_detachment_id(campaign, detachment_id + 1),
            unit_type_id=options.cavalry_type.id,
            soldiers=project.cavalry,
            name=f"{options.army_name} Cavalry",
        )
        detachments.append(cav_det)

    rules = options.rules
    army = Army(
        id=army_id,
        campaign_id=campaign.id,
        commander_id=commander.id,
        current_hex_id=project.rally_hex_id,
        detachments=detachments,
        status=ArmyStatus.IDLE,
        morale_current=rules.morale.default_resting,
        morale_resting=rules.morale.default_resting,
        morale_max=rules.morale.default_max,
        supplies_current=0,
        supplies_capacity=0,
        daily_supply_consumption=0,
        loot_carried=0,
        noncombatant_count=project.noncombatants,
        noncombatant_percentage=rules.supply.base_noncombatant_ratio,
        status_effects={},
    )

    campaign.armies[army.id] = army
    commander.current_hex_id = project.rally_hex_id

    snapshot = supply.build_supply_snapshot(campaign, army, rules)
    army.supplies_capacity = snapshot.capacity
    army.daily_supply_consumption = snapshot.consumption
    army.column_length_miles = snapshot.column_length_miles
    army.supplies_current = snapshot.consumption * 14

    detail = f"army {options.army_name} raised with {project.infantry} infantry"
    if project.cavalry:
        detail += f" and {project.cavalry} cavalry"

    campaign.recruitments.pop(project.id, None)

    return RecruitmentCompletion(army=army, detail=detail)


# ---------------------------------------------------------------------------
# Helpers


def _eligible_hexes(campaign, stronghold: Stronghold) -> list[HexID]:
    stronghold_hex = campaign.map.hexes.get(stronghold.hex_id)
    if stronghold_hex is None:
        return []
    stronghold_coord = HexCoord(q=stronghold_hex.q, r=stronghold_hex.r)

    priority = _stronghold_priority(stronghold.type)
    eligible: list[HexID] = []

    for hex_tile in campaign.map.hexes.values():
        if hex_tile.controlling_faction_id != stronghold.controlling_faction_id:
            continue
        if hex_tile.settlement <= 0:
            continue
        hex_coord = HexCoord(q=hex_tile.q, r=hex_tile.r)
        distance_to_current = hex_distance(hex_coord, stronghold_coord)
        closer_elsewhere = False
        for other in campaign.strongholds.values():
            if other.id == stronghold.id:
                continue
            other_hex = campaign.map.hexes.get(other.hex_id)
            if other_hex is None:
                continue
            other_coord = HexCoord(q=other_hex.q, r=other_hex.r)
            distance_other = hex_distance(hex_coord, other_coord)
            if distance_other < distance_to_current:
                closer_elsewhere = True
                break
            if distance_other == distance_to_current:
                other_priority = _stronghold_priority(other.type)
                if other_priority > priority or (
                    other_priority == priority and int(other.id) < int(stronghold.id)
                ):
                    closer_elsewhere = True
                    break
        if not closer_elsewhere:
            eligible.append(hex_tile.id)

    return eligible


def _hex_settlement(campaign, hex_id: HexID) -> int:
    hex_tile = campaign.map.hexes.get(hex_id)
    return hex_tile.settlement if hex_tile else 0


def _stronghold_priority(stronghold_type: StrongholdType) -> int:
    ranking = {
        StrongholdType.FORTRESS: 3,
        StrongholdType.CITY: 2,
        StrongholdType.TOWN: 1,
    }
    return ranking.get(stronghold_type, 0)


def _round_to_nearest_hundred(value: float) -> int:
    return int(round(value / 100.0) * 100)


def _next_project_id(campaign) -> int:
    if not campaign.recruitments:
        return 1
    return max(campaign.recruitments) + 1


def _next_army_id(campaign) -> int:
    if not campaign.armies:
        return 1
    return max(int(key) if not isinstance(key, int) else key for key in campaign.armies) + 1


def _next_detachment_id(campaign, start: int | None = None) -> DetachmentID:
    existing = [int(det.id) for army in campaign.armies.values() for det in army.detachments]
    base = max(existing, default=0)
    if start is not None and start > base:
        base = start - 1
    return DetachmentID(base + 1)


def _should_revolt(campaign, hex_tile: Hex, rules: RulesConfig) -> bool:
    last_day = hex_tile.last_recruited_day
    if last_day is None:
        return False
    within_cooldown = campaign.current_day - last_day <= rules.recruitment.recruitment_cooldown_days
    if not within_cooldown:
        return False

    base_chance = rules.recruitment.revolt_chance
    recently = (
        hex_tile.last_control_change_day is not None
        and campaign.current_day - hex_tile.last_control_change_day
        <= rules.recruitment.recently_conquered_days
    )
    if recently:
        base_chance = min(6, base_chance * 2)

    if base_chance <= 0:
        return False

    seed = f"recruit-revolt:{int(hex_tile.id)}:{campaign.current_day}"
    result = roll_dice(seed, "1d6")
    return result["total"] <= base_chance


def _spawn_revolt(campaign, hex_tile: Hex, rules: RulesConfig) -> Army:
    faction_id = _next_faction_id(campaign)
    faction = Faction(
        id=faction_id,
        campaign_id=campaign.id,
        name=f"Rebels of Hex {int(hex_tile.id)}",
        color="#777777",
    )
    campaign.factions[faction.id] = faction

    commander_id = _next_commander_id(campaign)
    commander = Commander(
        id=commander_id,
        campaign_id=campaign.id,
        name=f"Rebel Leader {int(commander_id)}",
        faction_id=faction.id,
        age=30,
    )
    campaign.commanders[commander.id] = commander

    roll = roll_dice(
        f"revolt-size:{int(hex_tile.id)}:{campaign.current_day}",
        f"1d{rules.revolt_outcome.infantry_die_size}",
    )
    infantry = max(500, roll["total"] * rules.revolt_outcome.infantry_multiplier)

    det_id = _next_detachment_id(campaign)
    detachment = Detachment(
        id=det_id,
        unit_type_id=_default_infantry_type(campaign),
        soldiers=infantry,
    )

    army_id = _next_army_id(campaign)
    army = Army(
        id=army_id,
        campaign_id=campaign.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        detachments=[detachment],
        status=ArmyStatus.IDLE,
        morale_current=rules.morale.default_resting,
        morale_resting=rules.morale.default_resting,
        morale_max=rules.morale.default_max,
        supplies_current=0,
        supplies_capacity=0,
        daily_supply_consumption=0,
        loot_carried=0,
        noncombatant_count=int(infantry * rules.supply.base_noncombatant_ratio),
        status_effects={"revolt": True},
    )
    campaign.armies[army.id] = army
    commander.current_hex_id = hex_tile.id

    snapshot = supply.build_supply_snapshot(campaign, army, rules)
    army.supplies_capacity = snapshot.capacity
    army.daily_supply_consumption = snapshot.consumption
    army.supplies_current = snapshot.consumption * 14

    return army


def _next_faction_id(campaign) -> FactionID:
    if not campaign.factions:
        return FactionID(1)
    return FactionID(max(int(fid) for fid in campaign.factions) + 1)


def _next_commander_id(campaign) -> CommanderID:
    if not campaign.commanders:
        return CommanderID(1)
    return CommanderID(max(int(cid) for cid in campaign.commanders) + 1)


def _default_infantry_type(campaign) -> UnitTypeID:
    for unit_type in campaign.unit_types.values():
        if unit_type.category == "infantry":
            return unit_type.id
    if campaign.unit_types:
        return next(iter(campaign.unit_types))
    return UnitTypeID(1)
