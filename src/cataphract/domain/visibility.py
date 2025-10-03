"""Visibility domain logic for Cataphract.

Pure functions for scouting radius and visible hex calculations.
"""

from cataphract.domain.supply import detachment_has_ability
from cataphract.models.army import Army
from cataphract.models.commander import Trait
from cataphract.utils.hex_math import HexCoord, get_ring


def calculate_scouting_radius(
    army: Army, traits: list[Trait] | None = None, weather: str = "clear"
) -> int:
    """Calculate scouting radius in hexes.

    Base: 1 (current +1 adjacent).
    Cavalry: +1 (to 2).
    Outrider + cavalry: +1 (to 3).
    Bad weather: -1 (min 0); very bad: -2.
    Ranger ignores weather.

    Args:
        army: Scouting army
        traits: Commander traits
        weather: "clear", "bad", "very_bad"

    Returns:
        Radius in hexes (0-3 typically)
    """
    traits = traits or []
    has_cavalry = any(
        det.unit_type.category == "cavalry"
        or detachment_has_ability(det, "acts_as_cavalry_for_scouting")
        for det in army.detachments
    )
    base_radius = 2 if has_cavalry else 1  # Current + adjacent = radius 1; +1 ring =2 total

    # Outrider trait
    has_outrider = any(getattr(t, "name", "").lower() == "outrider" for t in traits)
    if has_outrider and has_cavalry:
        base_radius += 1

    # Weather penalties
    weather_mod = 0
    if weather == "bad":
        weather_mod = -1
    elif weather == "very_bad":
        weather_mod = -2

    has_ranger = any(getattr(t, "name", "").lower() == "ranger" for t in traits)
    if not has_ranger:
        base_radius += weather_mod

    return max(0, base_radius)


def get_visible_hexes(current_hex_q: int, current_hex_r: int, radius: int) -> set[tuple[int, int]]:
    """Get all hex coordinates within scouting radius.

    Uses axial coordinates and ring expansion.

    Args:
        current_hex_q: Current q coord
        current_hex_r: Current r coord
        radius: Scouting radius

    Returns:
        Set of (q, r) tuples
    """
    visible: set[tuple[int, int]] = set()
    center = HexCoord(q=current_hex_q, r=current_hex_r)

    for ring in range(radius + 1):  # Include current (ring 0)
        for hex_coord in get_ring(center, ring):
            visible.add((hex_coord.q, hex_coord.r))

    return visible
