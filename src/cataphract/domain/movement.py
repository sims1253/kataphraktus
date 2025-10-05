"""Movement rules for Cataphract armies."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cataphract.domain.enums import MovementType
from cataphract.domain.models import Army, Trait, UnitType, UnitTypeID
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice

COLUMN_LENGTH_CAP_THRESHOLD = 6.0


@dataclass(slots=True)
class MovementValidation:
    """Simple structure describing movement validation results."""

    valid: bool
    error: str | None = None


@dataclass(slots=True)
class MovementOptions:
    """Configuration for a movement calculation."""

    on_road: bool
    traits: Iterable[Trait] | None = None
    weather_modifier: int = 0
    rules: RulesConfig = DEFAULT_RULES


def calculate_daily_movement_miles(
    unit_types: dict[UnitTypeID, UnitType],
    army: Army,
    movement_type: MovementType,
    options: MovementOptions,
) -> float:
    """Calculate daily miles based on movement mode and composition."""

    traits = list(options.traits or [])
    movement = options.rules.movement

    if movement_type == MovementType.NIGHT and not options.on_road:
        return 0.0

    base_lookup = {
        MovementType.STANDARD: movement.road_standard_miles_per_day
        if options.on_road
        else movement.offroad_standard_miles_per_day,
        MovementType.FORCED: movement.road_forced_miles_per_day
        if options.on_road
        else movement.offroad_forced_miles_per_day,
        MovementType.NIGHT: movement.night_miles_per_day,
    }
    base_speed = base_lookup[movement_type]

    if movement_type == MovementType.NIGHT and _has_trait(traits, "night_marcher"):
        base_speed = movement.night_forced_miles_per_day

    if movement_type == MovementType.FORCED and _is_cavalry_only(unit_types, army):
        base_speed *= movement.cavalry_forced_multiplier

    if not _has_trait(traits, "ranger"):
        base_speed = max(0.0, base_speed + options.weather_modifier)

    column_length = _column_length(unit_types, army, traits, options.rules)
    if column_length > COLUMN_LENGTH_CAP_THRESHOLD:
        cap = (
            movement.column_capped_standard_speed
            if movement_type == MovementType.STANDARD
            else movement.column_capped_forced_speed
            if movement_type == MovementType.FORCED
            else base_speed
        )
        base_speed = min(base_speed, cap)

    return max(0.0, base_speed)


def calculate_fording_delay(
    unit_types: dict[UnitTypeID, UnitType],
    army: Army,
    *,
    traits: Iterable[Trait] | None = None,
) -> float:
    """Return the number of days required to ford a river."""

    traits = list(traits or [])
    slow_detachments = [
        det for det in army.detachments if not _acts_as_cavalry(unit_types, det.unit_type_id)
    ]

    if not slow_detachments:
        return 0.0

    if any(det.wagons > 0 for det in army.detachments):
        raise ValueError("wagons cannot ford rivers")

    total_infantry = sum(det.soldiers for det in slow_detachments)
    total_infantry_nc = total_infantry + army.noncombatant_count
    column_miles = total_infantry_nc / 5000.0
    return column_miles * 0.5


def validate_movement_order(
    unit_types: dict[UnitTypeID, UnitType],
    army: Army,
    *,
    off_road_legs: Iterable[bool],
    has_river_fords: Iterable[bool],
    is_night: bool,
) -> MovementValidation:
    """Validate an order against off-road and fording constraints."""

    total_wagons = sum(det.wagons for det in army.detachments)

    if is_night and any(off_road_legs):
        return MovementValidation(False, "Cannot night march off-road")

    if total_wagons > 0 and any(off_road_legs):
        return MovementValidation(False, "Cannot travel off-road with wagons")

    if total_wagons > 0 and any(has_river_fords):
        return MovementValidation(False, "Cannot ford rivers with wagons")

    if any(has_river_fords):
        try:
            calculate_fording_delay(unit_types, army)
        except ValueError as exc:  # pragma: no cover - handled above, kept for safety
            return MovementValidation(False, str(exc))

    return MovementValidation(True)


# ---------------------------------------------------------------------------
# Helpers


def _has_trait(traits: Iterable[Trait], name: str) -> bool:
    return any(getattr(trait, "name", "").lower() == name.lower() for trait in traits)


def _is_cavalry_only(unit_types: dict[UnitTypeID, UnitType], army: Army) -> bool:
    if not army.detachments:
        return False
    return all(
        _unit_category(unit_types, det.unit_type_id) == "cavalry" for det in army.detachments
    )


def _acts_as_cavalry(unit_types: dict[UnitTypeID, UnitType], unit_type_id: UnitTypeID) -> bool:
    abilities = _unit_abilities(unit_types, unit_type_id)
    if abilities.get("acts_as_cavalry_for_fording"):
        return True
    if abilities.get("acts_as_cavalry_for_foraging"):
        return True
    return _unit_category(unit_types, unit_type_id) == "cavalry"


def _unit_category(unit_types: dict[UnitTypeID, UnitType], unit_type_id: UnitTypeID) -> str:
    unit = unit_types.get(unit_type_id)
    return unit.category if unit else "infantry"


def _unit_abilities(
    unit_types: dict[UnitTypeID, UnitType], unit_type_id: UnitTypeID
) -> dict[str, object]:
    unit = unit_types.get(unit_type_id)
    return unit.special_abilities or {} if unit else {}


def _column_length(
    unit_types: dict[UnitTypeID, UnitType],
    army: Army,
    traits: Iterable[Trait],
    rules: RulesConfig,
) -> float:
    traits = list(traits)
    total_soldiers = sum(det.soldiers for det in army.detachments)
    total_cavalry = sum(
        det.soldiers
        for det in army.detachments
        if _unit_category(unit_types, det.unit_type_id) == "cavalry"
    )
    total_infantry = total_soldiers - total_cavalry
    total_wagons = sum(det.wagons for det in army.detachments)

    noncombatants = army.noncombatant_count
    if noncombatants <= 0:
        ratio = (
            rules.supply.spartan_ratio
            if _has_trait(traits, "spartan")
            else rules.supply.base_noncombatant_ratio
        )
        noncombatants = int(total_soldiers * ratio)

    infantry_nc_miles = (total_infantry + noncombatants) / 5000.0
    cavalry_miles = total_cavalry / 2000.0
    wagon_miles = total_wagons / 50.0
    column = max(infantry_nc_miles, cavalry_miles, wagon_miles)
    if _has_trait(traits, "logistician"):
        column *= 0.5
    return column


def should_take_wrong_fork(seed: str, *, rules: RulesConfig = DEFAULT_RULES) -> bool:
    """Return True if a night march should take the wrong fork."""

    chance = rules.movement.night_wrong_path_chance
    if chance <= 0:
        return False
    roll = roll_dice(seed, "1d6")["total"]
    return roll <= chance
