"""Supply and logistics rules implemented on the new domain models."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from cataphract.utils.hex_math import HexCoord, hex_distance, hexes_in_range

from .enums import ArmyStatus
from .models import Army, Campaign, HexID, Trait, UnitType, UnitTypeID
from .rules_config import DEFAULT_RULES, RulesConfig

# ---------------------------------------------------------------------------
# Data structures returned by the supply subsystem


@dataclass(slots=True)
class SupplySnapshot:
    """Summary data derived from the detachments of an army."""

    total_soldiers: int
    total_cavalry: int
    total_wagons: int
    noncombatants: int
    capacity: int
    consumption: int
    column_length_miles: float
    wizard_detachments: int


@dataclass(slots=True)
class ForageOutcome:
    """Return type for a foraging action."""

    success: bool
    supplies_gained: int
    foraged_hexes: list[HexID]
    failed_hexes: list[tuple[HexID, str]]
    revolt_triggered: bool


@dataclass(slots=True)
class TorchOutcome:
    """Return type for torching action."""

    success: bool
    torched_hexes: list[HexID]
    failed_hexes: list[tuple[HexID, str]]
    revolt_triggered: bool


# ---------------------------------------------------------------------------
# Core calculations


def build_supply_snapshot(
    campaign: Campaign, army: Army, rules: RulesConfig = DEFAULT_RULES
) -> SupplySnapshot:
    """Calculate capacity, consumption, and column length for an army."""

    unit_types = campaign.unit_types
    traits = _commander_traits(campaign, army)

    total_soldiers = sum(det.soldiers for det in army.detachments)
    total_cavalry = sum(
        det.soldiers
        for det in army.detachments
        if _unit_category(unit_types, det.unit_type_id) == "cavalry"
    )
    total_wagons = sum(det.wagons for det in army.detachments)

    noncombatants = _calculate_noncombatants(army, unit_types, traits, rules)
    totals = CompositionTotals(
        infantry=total_soldiers - total_cavalry,
        cavalry=total_cavalry,
        wagons=total_wagons,
        noncombatants=noncombatants,
    )
    capacity = _calculate_capacity(totals, traits, army, rules)
    consumption = _calculate_consumption(totals, rules)
    column_length = _calculate_column_length(totals, traits)
    wizards = _count_wizard_detachments(army, rules.supply.wizard_supply_encumbrance)

    return SupplySnapshot(
        total_soldiers=total_soldiers,
        total_cavalry=total_cavalry,
        total_wagons=total_wagons,
        noncombatants=noncombatants,
        capacity=capacity,
        consumption=consumption,
        column_length_miles=column_length,
        wizard_detachments=wizards,
    )


# ---------------------------------------------------------------------------
# Foraging & torching


RollD6 = Callable[[], int]
RECENTLY_CONQUERED_THRESHOLD = 90


@dataclass(slots=True)
class SupplyOptions:
    """Optional parameters for supply actions."""

    weather: str = "clear"
    roll_d6: Callable[[], int] | None = None
    rules: RulesConfig = DEFAULT_RULES


@dataclass(slots=True)
class CompositionTotals:
    """Aggregated detachment totals used by supply calculations."""

    infantry: int
    cavalry: int
    wagons: int
    noncombatants: int


@dataclass(slots=True)
class RevoltContext:
    """Parameters used when checking for revolt risk."""

    action: str
    roll_d6: Callable[[], int] | None
    rules: RulesConfig


def forage(
    campaign: Campaign,
    army: Army,
    target_hexes: Iterable[HexID],
    options: SupplyOptions | None = None,
) -> ForageOutcome:
    """Execute a foraging action against the provided hex ids.

    The function mutates the campaign state (army supplies and hex counters).
    Any revolt is signalled in the return value; creation of the rebel army is
    left to the caller so it can be orchestrated centrally.
    """

    options = options or SupplyOptions()
    rules = options.rules
    army_hex = campaign.map.hexes.get(army.current_hex_id)
    if army_hex is None:
        return ForageOutcome(False, 0, [], [(army.current_hex_id, "army hex missing")], False)

    unit_types = campaign.unit_types
    traits = _commander_traits(campaign, army)
    forage_range = _foraging_range(army, unit_types, traits, options.weather, rules)
    snapshot = build_supply_snapshot(campaign, army, rules)

    supplies_gained = 0
    successful: list[HexID] = []
    failed: list[tuple[HexID, str]] = []
    revolt = False

    for hex_id in target_hexes:
        target = campaign.map.hexes.get(hex_id)
        if target is None:
            failed.append((hex_id, "hex not found"))
            continue

        if _hex_distance(army_hex, target) > forage_range:
            failed.append((hex_id, "hex out of range"))
            continue

        if target.is_torched:
            failed.append((hex_id, "hex torched"))
            continue

        if target.foraging_times_remaining <= 0:
            failed.append((hex_id, "foraging exhausted"))
            continue

        if target.settlement <= 0:
            failed.append((hex_id, "no settlement"))
            continue

        revolt |= _check_revolt(
            campaign,
            army,
            target,
            RevoltContext(action="forage", roll_d6=options.roll_d6, rules=rules),
        )

        gained = target.settlement * rules.supply.foraging_multiplier
        if _has_trait(traits, "raider"):
            gained = int(gained * 1.10)

        target.foraging_times_remaining -= 1
        target.last_foraged_day = campaign.current_day
        supplies_gained += gained
        successful.append(hex_id)

    if supplies_gained:
        effective_capacity = army.supplies_capacity or snapshot.capacity
        army.supplies_current = min(effective_capacity, army.supplies_current + supplies_gained)

    return ForageOutcome(
        success=bool(successful),
        supplies_gained=supplies_gained,
        foraged_hexes=successful,
        failed_hexes=failed,
        revolt_triggered=revolt,
    )


def torch(
    campaign: Campaign,
    army: Army,
    target_hexes: Iterable[HexID],
    options: SupplyOptions | None = None,
) -> TorchOutcome:
    """Torch the supplied hex ids, mutating the campaign state."""

    options = options or SupplyOptions()
    rules = options.rules
    army_hex = campaign.map.hexes.get(army.current_hex_id)
    if army_hex is None:
        return TorchOutcome(False, [], [(army.current_hex_id, "army hex missing")], False)

    unit_types = campaign.unit_types
    traits = _commander_traits(campaign, army)
    torch_range = _foraging_range(army, unit_types, traits, options.weather, rules)

    torched: list[HexID] = []
    failed: list[tuple[HexID, str]] = []
    revolt = False

    for hex_id in target_hexes:
        target = campaign.map.hexes.get(hex_id)
        if target is None:
            failed.append((hex_id, "hex not found"))
            continue

        if _hex_distance(army_hex, target) > torch_range:
            failed.append((hex_id, "hex out of range"))
            continue

        revolt |= _check_revolt(
            campaign,
            army,
            target,
            RevoltContext(action="torch", roll_d6=options.roll_d6, rules=rules),
        )

        _apply_torch_effect(campaign, target, torch_range)
        torched.append(hex_id)

    if torched:
        army.status = ArmyStatus.TORCHING

    return TorchOutcome(
        success=bool(torched),
        torched_hexes=torched,
        failed_hexes=failed,
        revolt_triggered=revolt,
    )


# ---------------------------------------------------------------------------
# Helper functions


def _unit_category(unit_types: dict[UnitTypeID, UnitType], unit_type_id: UnitTypeID) -> str:
    unit = unit_types.get(unit_type_id)
    return getattr(unit, "category", "infantry") if unit else "infantry"


def _unit_abilities(
    unit_types: dict[UnitTypeID, UnitType], unit_type_id: UnitTypeID
) -> dict[str, object]:
    unit = unit_types.get(unit_type_id)
    abilities = getattr(unit, "special_abilities", None)
    return abilities or {}


def _commander_traits(campaign: Campaign, army: Army) -> list[Trait]:
    commander = campaign.commanders.get(army.commander_id)
    if commander is None:
        empty: list[Trait] = []
        return empty
    return commander.traits


def _has_trait(traits: Iterable[Trait], name: str) -> bool:
    return any(getattr(trait, "name", "").lower() == name.lower() for trait in traits)


def _calculate_noncombatants(
    army: Army,
    unit_types: dict[UnitTypeID, UnitType],
    traits: list[Trait],
    rules: RulesConfig,
) -> int:
    total_soldiers = sum(det.soldiers for det in army.detachments)
    total_wagons = sum(det.wagons for det in army.detachments)

    exclusive_skirmisher = (
        total_wagons == 0
        and army.detachments
        and all(
            _unit_abilities(unit_types, det.unit_type_id).get("offroad_full_speed")
            and _unit_abilities(unit_types, det.unit_type_id).get("acts_as_cavalry_for_foraging")
            for det in army.detachments
        )
    )

    if exclusive_skirmisher:
        ratio = rules.supply.exclusive_skirmisher_ratio
    elif _has_trait(traits, "spartan"):
        ratio = rules.supply.spartan_ratio
    else:
        ratio = rules.supply.base_noncombatant_ratio

    return int(total_soldiers * ratio)


def _calculate_capacity(
    totals: CompositionTotals,
    traits: list[Trait],
    army: Army,
    rules: RulesConfig,
) -> int:
    supply_rules = rules.supply
    infantry_nc_capacity = (totals.infantry + totals.noncombatants) * supply_rules.infantry_capacity
    cavalry_capacity = totals.cavalry * supply_rules.cavalry_capacity
    wagon_capacity = totals.wagons * supply_rules.wagon_capacity
    total = infantry_nc_capacity + cavalry_capacity + wagon_capacity

    if _has_trait(traits, "logistician"):
        total = int(total * 1.20)

    total -= _count_wizard_detachments(army, supply_rules.wizard_supply_encumbrance)
    return max(0, total)


def _calculate_consumption(totals: CompositionTotals, rules: RulesConfig) -> int:
    supply_rules = rules.supply
    return (
        (totals.infantry + totals.noncombatants) * supply_rules.infantry_consumption
        + totals.cavalry * supply_rules.cavalry_consumption
        + totals.wagons * supply_rules.wagon_consumption
    )


def _calculate_column_length(totals: CompositionTotals, traits: list[Trait]) -> float:
    infantry_nc_miles = (totals.infantry + totals.noncombatants) / 5000.0
    cavalry_miles = totals.cavalry / 2000.0
    wagon_miles = totals.wagons / 50.0
    column = max(infantry_nc_miles, cavalry_miles, wagon_miles)
    if _has_trait(traits, "logistician"):
        column *= 0.5
    return column


def _count_wizard_detachments(army: Army, supplies_equivalent: int) -> int:
    count = 0
    for det in army.detachments:
        instance = det.instance_data or {}
        if instance.get("supplies_equivalent") == supplies_equivalent:
            count += 1
    return count


def _foraging_range(
    army: Army,
    unit_types: dict[UnitTypeID, UnitType],
    traits: list[Trait],
    weather: str,
    rules: RulesConfig,
) -> int:
    base = rules.visibility.base_radius
    has_cavalry = any(
        _unit_category(unit_types, det.unit_type_id) == "cavalry"
        or _unit_abilities(unit_types, det.unit_type_id).get("acts_as_cavalry_for_foraging")
        for det in army.detachments
    )
    if has_cavalry:
        base += rules.visibility.cavalry_bonus
    if has_cavalry and _has_trait(traits, "outrider"):
        base += rules.visibility.outrider_bonus

    weather_penalty = 0
    if weather in {"bad", "storm"}:
        weather_penalty = rules.visibility.bad_weather_penalty
    elif weather == "very_bad":
        weather_penalty = rules.visibility.very_bad_weather_penalty

    if _has_trait(traits, "ranger"):
        weather_penalty = 0

    return max(0, base - weather_penalty)


def _hex_distance(a_hex, b_hex) -> int:
    a = HexCoord(q=a_hex.q, r=a_hex.r)
    b = HexCoord(q=b_hex.q, r=b_hex.r)
    return hex_distance(a, b)


def _check_revolt(
    campaign: Campaign,
    army: Army,
    target_hex,
    context: RevoltContext,
) -> bool:
    rules = context.rules
    supply_rules = rules.supply
    if context.action == "forage":
        last_day = target_hex.last_foraged_day
        within_year = (
            last_day is not None
            and campaign.current_day - last_day <= supply_rules.revolt_cooldown_days
        )
        if not within_year:
            return False
        base_chance = supply_rules.forage_revolt_chance_repeat
    else:  # torch
        base_chance = supply_rules.torch_revolt_chance

    roll_d6 = context.roll_d6
    if roll_d6 is None:
        return False  # deterministic no-revolt unless caller injects RNG

    territory = _classify_territory(campaign, army, target_hex)
    if territory == "hostile":
        modifier = (
            supply_rules.forage_revolt_hostile_modifier
            if context.action == "forage"
            else supply_rules.torch_revolt_hostile_modifier
        )
        base_chance += modifier

    if _has_trait(_commander_traits(campaign, army), "honorable"):
        base_chance = max(0, base_chance - 1)

    roll = roll_d6()
    return roll <= base_chance


def _classify_territory(campaign: Campaign, army: Army, target_hex) -> str:
    faction_id = target_hex.controlling_faction_id
    commander = campaign.commanders.get(army.commander_id)
    if faction_id is None:
        return "neutral"
    if commander and commander.faction_id == faction_id:
        if (
            target_hex.last_control_change_day is not None
            and campaign.current_day - target_hex.last_control_change_day
            <= RECENTLY_CONQUERED_THRESHOLD
        ):
            return "recently_conquered"
        return "friendly"
    # TODO: consult faction relations for allied status
    return "hostile"


def _apply_torch_effect(campaign: Campaign, target_hex, torch_range: int) -> None:
    target_hex.is_torched = True
    target_hex.foraging_times_remaining = 0
    target_hex.last_torched_day = campaign.current_day

    center = HexCoord(q=target_hex.q, r=target_hex.r)
    affected_coords = hexes_in_range(center, torch_range)
    for coord in affected_coords:
        if (coord.q, coord.r) == (target_hex.q, target_hex.r):
            continue
        affected = next(
            (hx for hx in campaign.map.hexes.values() if hx.q == coord.q and hx.r == coord.r),
            None,
        )
        if affected is None:
            continue
        affected.is_torched = True
        affected.foraging_times_remaining = 0
        affected.last_torched_day = campaign.current_day
