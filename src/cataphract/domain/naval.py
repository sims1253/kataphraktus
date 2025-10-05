"""Naval transport and movement rules."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain.enums import NavalStatus
from cataphract.domain.models import Army, Campaign, HexID, Ship
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.hex_math import HexCoord, hex_distance

DAY_PARTS_PER_DAY = 4
HEX_MILES = 6


@dataclass(slots=True)
class NavalActionResult:
    """Outcome for embark/disembark/naval movement."""

    success: bool
    detail: str


class NavalError(RuntimeError):
    """Raised when a naval action is invalid."""


def embark_army(
    _campaign: Campaign,
    army: Army,
    ship: Ship,
    *,
    rules: RulesConfig = DEFAULT_RULES,
) -> NavalActionResult:
    """Embark an army onto a ship if both are co-located."""

    if army.embarked_ship_id is not None:
        return NavalActionResult(False, "army already embarked")
    if ship.embarked_army_id is not None:
        return NavalActionResult(False, "ship already transporting an army")
    if army.current_hex_id != ship.current_hex_id:
        return NavalActionResult(False, "army and ship must share a hex")
    if ship.status not in {NavalStatus.AVAILABLE, NavalStatus.TRANSPORTING}:
        return NavalActionResult(False, f"ship status {ship.status} disallows embarkation")

    army.embarked_ship_id = ship.id
    ship.embarked_army_id = army.id
    ship.status = NavalStatus.TRANSPORTING
    ship.travel_days_remaining = max(ship.travel_days_remaining, rules.naval.embark_days)

    return NavalActionResult(True, "army embarked")


def disembark_army(
    _campaign: Campaign,
    army: Army,
    ship: Ship,
    *,
    rules: RulesConfig = DEFAULT_RULES,
) -> NavalActionResult:
    """Disembark an army from a ship."""

    if army.embarked_ship_id != ship.id or ship.embarked_army_id != army.id:
        return NavalActionResult(False, "army not embarked on specified ship")
    if ship.travel_days_remaining > 0:
        return NavalActionResult(False, "ship is still en route")

    army.embarked_ship_id = None
    ship.embarked_army_id = None
    ship.status = NavalStatus.AVAILABLE
    ship.travel_days_remaining = rules.naval.disembark_days
    army.current_hex_id = ship.current_hex_id

    return NavalActionResult(True, "army disembarked")


def set_course(
    campaign: Campaign,
    ship: Ship,
    route: list[HexID],
    *,
    rules: RulesConfig = DEFAULT_RULES,
) -> NavalActionResult:
    """Assign a sailing route to a ship."""

    if not route:
        return NavalActionResult(False, "route required")
    if ship.embarked_army_id and campaign.armies.get(ship.embarked_army_id) is None:
        return NavalActionResult(False, "embarked army missing")

    total_miles = 0
    current = ship.current_hex_id
    for target in route:
        start_hex = campaign.map.hexes.get(current)
        end_hex = campaign.map.hexes.get(target)
        if start_hex is None or end_hex is None:
            return NavalActionResult(False, "route references unknown hex")
        start_coord = _to_coord(start_hex)
        end_coord = _to_coord(end_hex)
        total_miles += max(1, hex_distance(start_coord, end_coord)) * HEX_MILES
        current = target

    speed = rules.naval.friendly_miles_per_day
    ship.current_route = route
    ship.travel_days_remaining = max(0.0, total_miles / speed)
    ship.movement_points_remaining = 1.0
    ship.status = NavalStatus.TRANSPORTING if ship.embarked_army_id else NavalStatus.AVAILABLE

    return NavalActionResult(True, f"course set for {len(route)} leg(s)")


def advance_ships(
    campaign: Campaign,
    *,
    rules: RulesConfig = DEFAULT_RULES,
    day_fraction: float = 1 / DAY_PARTS_PER_DAY,
) -> None:
    """Advance ship travel timers and move embarked armies with them."""

    _ = rules

    for ship in campaign.ships.values():
        if not ship.current_route:
            if ship.travel_days_remaining > 0:
                ship.travel_days_remaining = max(0.0, ship.travel_days_remaining - day_fraction)
            continue

        ship.travel_days_remaining = max(0.0, ship.travel_days_remaining - day_fraction)
        if ship.travel_days_remaining > 0:
            continue

        destination = ship.current_route[-1]
        ship.current_hex_id = destination
        ship.current_route.clear()
        ship.movement_points_remaining = 0.0
        ship.status = (
            NavalStatus.AVAILABLE if ship.embarked_army_id is None else NavalStatus.TRANSPORTING
        )
        if ship.embarked_army_id is not None:
            army = campaign.armies.get(ship.embarked_army_id)
            if army is not None:
                army.current_hex_id = destination
                army.is_blockaded = False


def _to_coord(hex_obj) -> HexCoord:
    return HexCoord(q=hex_obj.q, r=hex_obj.r)
