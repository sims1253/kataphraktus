"""Movement domain logic for Cataphract.

Pure functions for movement calculations: speeds, column effects, fording, etc.
"""

from enum import Enum

from cataphract.domain.supply import (
    calculate_column_length,
    calculate_total_wagons,
    detachment_has_ability,
)
from cataphract.models.army import Army
from cataphract.models.commander import Trait

# Movement constants
COLUMN_LENGTH_CAP_THRESHOLD = 6  # miles; columns >6 miles travel at reduced speed


class MovementType(Enum):
    STANDARD = "standard"  # 12 miles/day on road, 6 off-road
    FORCED = "forced"  # 18 miles/day on road, 9 off-road; morale cost
    NIGHT = "night"  # 6 miles/night standard, 12 forced; morale check


def calculate_daily_movement_miles(
    army: Army,
    movement_type: MovementType,
    on_road: bool,
    traits: list[Trait] | None = None,
    weather_modifier: int = 0,
) -> float:
    """Calculate daily movement in miles.

    Base: 12 road/6 off-road standard; 18/9 forced; 6/12 night.
    Cavalry-only doubles forced. Weather -1/-2 miles. >6 mile column caps at 6/12.

    Args:
        army: Army moving
        movement_type: Type of movement
        on_road: True if on road
        traits: Commander traits (e.g., Ranger ignores weather)
        weather_modifier: -1 bad, -2 very bad

    Returns:
        Miles per day
    """
    traits = traits or []
    base_speed = {
        MovementType.STANDARD: 12 if on_road else 6,
        MovementType.FORCED: 18 if on_road else 9,
        MovementType.NIGHT: 6 if on_road else 0,  # Cannot off-road at night
    }[movement_type]

    # Cavalry-only double forced
    is_cavalry_only = all(det.unit_type.category == "cavalry" for det in army.detachments)
    if movement_type == MovementType.FORCED and is_cavalry_only:
        base_speed *= 2

    # Weather penalty
    has_ranger = any(getattr(t, "name", "").lower() == "ranger" for t in traits)
    if not has_ranger:
        base_speed += weather_modifier  # Negative modifier

    base_speed = max(0, base_speed)

    # Column length cap: >6 miles -> 6 standard/12 forced
    column_miles = calculate_column_length(army, traits)
    if column_miles > COLUMN_LENGTH_CAP_THRESHOLD:
        capped_speed = (
            6
            if movement_type == MovementType.STANDARD
            else 12
            if movement_type == MovementType.FORCED
            else base_speed
        )
        return min(base_speed, capped_speed)

    return base_speed


def calculate_fording_delay(army: Army, traits: list[Trait] | None = None) -> float:
    """Calculate days to ford river: 0.5 days per mile of infantry+NC column.

    Cavalry at normal speed; wagons cannot ford.
    """
    traits = traits or []
    slow_detachments = [
        det
        for det in army.detachments
        if det.unit_type.category != "cavalry"
        and not detachment_has_ability(det, "acts_as_cavalry_for_fording")
    ]

    if not slow_detachments:
        return 0.0

    total_infantry = sum(det.soldier_count for det in slow_detachments)
    total_infantry_nc = total_infantry + army.noncombatant_count
    column_miles_infantry = total_infantry_nc / 5000.0
    delay_days = column_miles_infantry * 0.5

    # Wagons prevent fording entirely if present
    if calculate_total_wagons(army) > 0:
        raise ValueError("Army has wagons; cannot ford rivers")

    return delay_days


def validate_movement_order(
    army: Army,
    off_road_legs: list[bool],
    has_river_fords: list[bool],
    is_night: bool,
    traits: list[Trait] | None = None,
) -> tuple[bool, str | None]:
    """Validate movement order against rules.

    Rejects off-road with wagons, night off-road, river fords with wagons.

    Args:
        army: Moving army
        off_road_legs: List of True if leg off-road
        has_river_fords: List of True if leg has river ford
        is_night: True if night march
        traits: Traits (faction exceptions possible)

    Returns:
        (valid, error_msg)
    """
    traits = traits or []
    total_wagons = calculate_total_wagons(army)

    if any(off_road_legs) and total_wagons > 0:
        # Faction exceptions via traits/special_rules (future)
        return False, "Cannot travel off-road with wagons"

    if is_night and any(off_road_legs):
        return False, "Cannot night march off-road"

    if any(has_river_fords) and total_wagons > 0:
        return False, "Cannot ford rivers with wagons"

    return True, None
