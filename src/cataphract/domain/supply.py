"""Supply domain logic for Cataphract.

This module contains pure functions for supply calculations, separated from
services for testability and reusability.
"""

from typing import Any

from cataphract.models.army import Army, Detachment
from cataphract.models.commander import Trait

WIZARD_SUPPLY_ENCUMBRANCE = 1000


def calculate_total_soldiers(army: Army) -> int:
    """Calculate total soldier count across all detachments."""
    return sum(det.soldier_count for det in army.detachments)


def calculate_total_cavalry(army: Army) -> int:
    """Calculate total cavalry count across all cavalry detachments."""
    return sum(det.soldier_count for det in army.detachments if det.unit_type.category == "cavalry")


def calculate_total_wagons(army: Army) -> int:
    """Calculate total wagon count across all detachments."""
    return sum(det.wagon_count for det in army.detachments)


def calculate_noncombatant_count(army: Army, traits: list[Trait] | None = None) -> int:
    """Calculate noncombatant count based on army composition and traits.

    Default is 25% of soldiers (12.5% with Spartan trait).
    For exclusive skirmisher armies with no wagons, it's 10%.
    """
    traits = traits or []
    total_soldiers = calculate_total_soldiers(army)
    total_wagons = calculate_total_wagons(army)

    # Check if exclusive skirmisher army
    if _is_exclusive_skirmisher_army(army) and total_wagons == 0:
        return int(total_soldiers * 0.10)

    # Check for Spartan trait (trait catalog stores lowercase names)
    has_spartan = any(getattr(trait, "name", "").lower() == "spartan" for trait in traits)
    percentage = 0.125 if has_spartan else 0.25

    return int(total_soldiers * percentage)


def calculate_supply_capacity(army: Army, traits: list[Trait] | None = None) -> int:
    """Calculate total supply capacity of the army.

    Base capacity: 15 per infantry/NC, 75 per cavalry, 1000 per wagon.
    Logistician trait: +20% capacity.
    Wizard encumbrance: -1000 per wizard detachment.
    """
    traits = traits or []
    total_soldiers = calculate_total_soldiers(army)
    total_cavalry = calculate_total_cavalry(army)
    total_infantry = total_soldiers - total_cavalry
    noncombatants = calculate_noncombatant_count(army, traits)
    total_wagons = calculate_total_wagons(army)

    # Base capacity calculations
    infantry_nc_capacity = (total_infantry + noncombatants) * 15
    cavalry_capacity = total_cavalry * 75
    wagon_capacity = total_wagons * 1000

    total_capacity = infantry_nc_capacity + cavalry_capacity + wagon_capacity

    # Apply Logistician bonus (+20%)
    has_logistician = any(getattr(trait, "name", "").lower() == "logistician" for trait in traits)
    if has_logistician:
        total_capacity = int(total_capacity * 1.20)

    # Subtract wizard encumbrance (1000 per wizard detachment)
    wizard_count = _count_wizard_detachments(army)
    total_capacity -= wizard_count * 1000

    return max(0, total_capacity)


def calculate_daily_consumption(army: Army) -> int:
    """Calculate daily supply consumption.

    1 per infantry/NC, 10 per cavalry, 10 per wagon.
    """
    total_soldiers = calculate_total_soldiers(army)
    total_cavalry = calculate_total_cavalry(army)
    total_infantry = total_soldiers - total_cavalry
    noncombatants = army.noncombatant_count  # Use current NC count
    total_wagons = calculate_total_wagons(army)

    infantry_nc_consumption = (total_infantry + noncombatants) * 1
    cavalry_consumption = total_cavalry * 10
    wagon_consumption = total_wagons * 10

    return infantry_nc_consumption + cavalry_consumption + wagon_consumption


def is_army_undersupplied(army: Army) -> bool:
    """Check if army is undersupplied.

    True if: supplies_current < daily_consumption OR days_without_supplies > 0.
    """
    return (army.supplies_current < army.daily_supply_consumption) or (
        army.days_without_supplies > 0
    )


def calculate_column_length(army: Army, traits: list[Trait] | None = None) -> float:
    """Calculate the length of an army column in miles.

    Column length: 1 mile per 5,000 infantry+NC, 2,000 cavalry, 50 wagons.
    Army column length is determined by the longest component.

    Args:
        army: Army to calculate column length for
        traits: Commander traits (affects calculation)

    Returns:
        Column length in miles
    """
    traits = traits or []

    # Calculate component counts
    total_soldiers = calculate_total_soldiers(army)
    total_cavalry = calculate_total_cavalry(army)
    total_infantry = total_soldiers - total_cavalry
    noncombatants = calculate_noncombatant_count(army, traits)
    total_wagons = calculate_total_wagons(army)

    # Calculate column length for each component
    infantry_nc_miles = (total_infantry + noncombatants) / 5000.0
    cavalry_miles = total_cavalry / 2000.0
    wagon_miles = total_wagons / 50.0

    # Army column length is determined by the longest component
    column_miles = max(infantry_nc_miles, cavalry_miles, wagon_miles)

    # Apply Logistician trait: half column length
    has_logistician = any(getattr(trait, "name", "").lower() == "logistician" for trait in traits)
    if has_logistician:
        column_miles = column_miles * 0.5

    return column_miles


def _is_exclusive_skirmisher_army(army: Army) -> bool:
    """Check if army consists entirely of skirmisher detachments."""
    if not army.detachments:
        return False

    return all(detachment_has_ability(det, "skirmisher") for det in army.detachments)


def _count_wizard_detachments(army: Army) -> int:
    """Count wizard detachments based on their supplies equivalence."""

    count = 0
    for det in army.detachments:
        if (
            det.instance_data
            and det.instance_data.get("supplies_equivalent") == WIZARD_SUPPLY_ENCUMBRANCE
        ):
            count += 1
    return count


def detachment_has_ability(detachment: Detachment, ability: str) -> bool:
    """Return True if the detachment advertises the given special ability flag."""

    abilities: dict[str, Any] | None = getattr(detachment.unit_type, "special_abilities", None)
    if not isinstance(abilities, dict):
        return False
    return bool(abilities.get(ability))
