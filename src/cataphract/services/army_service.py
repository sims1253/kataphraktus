"""Army Management Service for Cataphract.

This module provides functions for managing army composition, supply calculations,
and army operations like splitting, merging, and transferring supplies.
"""

from sqlalchemy.orm import Session, attributes

from cataphract.domain.supply import (
    _is_exclusive_skirmisher_army,
    calculate_column_length,
    calculate_daily_consumption,
    calculate_noncombatant_count,
    calculate_supply_capacity,
    calculate_total_soldiers,
    calculate_total_wagons,
)
from cataphract.models import Detachment, Game, Hex, UnitType
from cataphract.models.army import Army
from cataphract.models.commander import Commander, Trait
from cataphract.utils.rng import generate_seed, roll_dice

# Constants
WIZARD_SUPPLY_ENCUMBRANCE = 1000
RECENTLY_CONQUERED_DAYS = 90  # Days after conquest for increased revolt risk
DEFAULT_STARTING_MORALE = 9  # Default morale for new armies
RECRUITMENT_COOLDOWN_DAYS = 365  # Days between recruitments from same hex
INITIAL_SUPPLIES_PER_SOLDIER = 20  # Initial supplies when raising army


def split_army(
    army: Army,
    new_commander_id: int,
    detachment_ids: list[int],
    session: Session,
) -> Army:
    """Split an army by moving specified detachments to a new army.

    Creates a new army with the specified detachments and updates both armies.

    Args:
        army: The source army to split from
        new_commander_id: Commander ID for the new army
        detachment_ids: List of detachment IDs to move to new army
        session: Database session

    Returns:
        The newly created army

    Raises:
        ValueError: If detachment_ids is empty or contains invalid IDs
    """
    try:
        if not detachment_ids:
            raise ValueError("Must specify at least one detachment to split")

        # Validate detachments belong to this army
        detachments_to_move = [det for det in army.detachments if det.id in detachment_ids]
        if len(detachments_to_move) != len(detachment_ids):
            raise ValueError("Some detachment IDs do not belong to this army")

        # Cannot split all detachments
        if len(detachments_to_move) == len(army.detachments):
            raise ValueError("Cannot split all detachments from an army")

        # Create new army
        new_army = Army(
            game_id=army.game_id,
            commander_id=new_commander_id,
            current_hex_id=army.current_hex_id,
            status="idle",
            morale_current=army.morale_current,
            morale_resting=army.morale_resting,
            morale_max=army.morale_max,
            noncombatant_percentage=army.noncombatant_percentage,
        )
        session.add(new_army)
        session.flush()  # Get ID for new army

        # Move detachments
        for det in detachments_to_move:
            det.army_id = new_army.id

        # Apply commander traits to new army
        _apply_commander_traits_to_army(new_army, new_commander_id, session)

        # Update both armies
        update_army_composition(army, session)
        update_army_composition(new_army, session)

        session.commit()
        return new_army
    except Exception:
        session.rollback()
        raise


def merge_armies(target_army: Army, source_army: Army, session: Session) -> None:
    """Merge source army into target army and delete source army.

    All detachments from source army are moved to target army.

    Args:
        target_army: The army to merge into
        source_army: The army to merge from (will be deleted)
        session: Database session

    Raises:
        ValueError: If armies are in different hexes or games
    """
    try:
        if target_army.current_hex_id != source_army.current_hex_id:
            raise ValueError("Armies must be in the same hex to merge")

        if target_army.game_id != source_army.game_id:
            raise ValueError("Armies must be in the same game to merge")

        # Move all detachments to target army
        detachments_to_move = list(source_army.detachments)  # Create list copy
        for det in detachments_to_move:
            det.army_id = target_army.id

        # Transfer supplies
        target_army.supplies_current += source_army.supplies_current

        # Commit detachment transfers first (this saves the new army_id before cascade delete)
        session.commit()

        # Now delete the source army (detachments already have new army_id)
        session.delete(source_army)
        session.commit()

        # Explicitly expire all attributes to force reload
        session.expire(target_army)

        # Update target army composition (will reload detachments and commit again)
        update_army_composition(target_army, session)

        # Expire again after update to ensure caller gets fresh data
        session.expire(target_army)
    except Exception:
        session.rollback()
        raise


def transfer_supplies(
    from_army: Army,
    to_army: Army,
    amount: int,
    session: Session,
) -> None:
    """Transfer supplies from one army to another.

    Args:
        from_army: The army to transfer supplies from
        to_army: The army to transfer supplies to
        amount: Amount of supplies to transfer
        session: Database session

    Raises:
        ValueError: If amount is invalid or from_army has insufficient supplies
    """
    try:
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        if from_army.supplies_current < amount:
            raise ValueError(
                f"From army has insufficient supplies: {from_army.supplies_current} < {amount}"
            )

        # Check capacity of receiving army
        if to_army.supplies_current + amount > to_army.supplies_capacity:
            raise ValueError(
                f"To army does not have enough capacity: "
                f"{to_army.supplies_current + amount} > {to_army.supplies_capacity}"
            )

        # Perform transfer
        from_army.supplies_current -= amount
        to_army.supplies_current += amount

        session.commit()
    except Exception:
        session.rollback()
        raise


def update_army_composition(army: Army, session: Session) -> None:
    """Recalculate all derived fields for an army.

    Updates: soldiers, cavalry, wagons, noncombatants, column length,
    supply capacity, and daily consumption.

    Args:
        army: The army to update
        session: Database session
    """
    try:
        # Get commander traits if available
        traits: list[Trait] = []
        if army.commander and hasattr(army.commander, "traits"):
            traits = [ct.trait for ct in army.commander.traits]

        # Update noncombatant count
        army.noncombatant_count = calculate_noncombatant_count(army, traits)

        # Update column length
        army.column_length_miles = calculate_column_length(army, traits)

        # Update supply capacity
        army.supplies_capacity = calculate_supply_capacity(army, traits)

        # Update daily consumption
        army.daily_supply_consumption = calculate_daily_consumption(army)

        # Cap supplies at capacity
        army.supplies_current = min(army.supplies_current, army.supplies_capacity)

        # Store exclusive skirmisher status in status_effects
        if _is_exclusive_skirmisher_army(army) and calculate_total_wagons(army) == 0:
            if army.status_effects is None:
                army.status_effects = {}
            army.status_effects["exclusive_skirmisher"] = True  # type: ignore[index]
            # Mark as modified for SQLAlchemy to track the change
            attributes.flag_modified(army, "status_effects")
        # Remove exclusive skirmisher status if army no longer qualifies
        elif army.status_effects and "exclusive_skirmisher" in army.status_effects:
            del army.status_effects["exclusive_skirmisher"]
            # Mark as modified for SQLAlchemy to track the change
            attributes.flag_modified(army, "status_effects")

        session.commit()
    except Exception:
        session.rollback()
        raise


def validate_army_composition(army: Army) -> tuple[bool, str | None]:
    """Validate army composition.

    Checks:
    - Army has at least one detachment
    - Supplies don't exceed capacity
    - All detachments have valid data

    Args:
        army: The army to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for detachments
    if not army.detachments:
        return False, "Army must have at least one detachment"

    # Check supplies vs capacity
    if army.supplies_current > army.supplies_capacity:
        return (
            False,
            f"Supplies exceed capacity: {army.supplies_current} > {army.supplies_capacity}",
        )

    # Validate detachments
    for det in army.detachments:
        if det.soldier_count < 0:
            return False, f"Detachment {det.name} has negative soldier count"

        if det.wagon_count < 0:
            return False, f"Detachment {det.name} has negative wagon count"

    return True, None


def transfer_loot(
    from_army: Army,
    to_army: Army,
    amount: int,
    session: Session,
) -> None:
    """Transfer loot from one army to another.

    Args:
        from_army: The army to transfer loot from
        to_army: The army to transfer loot to
        amount: Amount of loot to transfer
        session: Database session

    Raises:
        ValueError: If amount is invalid or from_army has insufficient loot
    """
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    if from_army.loot_carried < amount:
        raise ValueError(f"From army has insufficient loot: {from_army.loot_carried} < {amount}")

    # Perform transfer
    from_army.loot_carried -= amount
    to_army.loot_carried += amount

    session.commit()


def raise_army(
    game_id: int, commander_id: int, hex_id: int, composition: list[dict], session: Session
) -> Army:
    """Raise a new army from settlements in nearby hexes according to game rules.

    Args:
        game_id: The game this army belongs to
        commander_id: The commander leading this army
        hex_id: The hex where the army is raised
        composition: List of dictionaries with unit_type, count, and optionally wagons
        session: Database session

    Returns:
        The newly created army

    Raises:
        ValueError: If revolt is triggered
    """
    # Get the hex
    hex_obj = session.query(Hex).filter(Hex.id == hex_id).first()
    if not hex_obj:
        raise ValueError(f"Hex {hex_id} not found")

    game = session.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise ValueError(f"Game {game_id} not found")

    current_day = game.current_day
    current_part = game.current_day_part

    # Check for revolt risk
    revolt_chance = 1  # Base 1-in-6
    is_recently_conquered = (
        hex_obj.controlling_faction_id is not None
        and hex_obj.last_control_change_day is not None
        and (current_day - hex_obj.last_control_change_day) <= RECENTLY_CONQUERED_DAYS
    )
    if is_recently_conquered:
        revolt_chance = 2  # 2-in-6 in recently conquered

    # Check if second recruitment within year
    if (
        hex_obj.last_recruited_day is not None
        and (current_day - hex_obj.last_recruited_day) <= RECRUITMENT_COOLDOWN_DAYS
    ):
        # Honorable trait reduces chance
        commander = session.query(Commander).filter(Commander.id == commander_id).first()
        has_honorable = (
            any(getattr(ct.trait, "name", "").lower() == "honorable" for ct in commander.traits)
            if commander
            else False
        )
        revolt_chance = max(0, revolt_chance - 1 if has_honorable else revolt_chance)
        revolt_seed = generate_seed(
            game_id,
            current_day,
            current_part,
            f"raise_army_revolt_check:{hex_id}:{commander_id}",
        )
        revolt_roll = roll_dice(revolt_seed, "1d6")["total"]
        if revolt_roll <= revolt_chance:
            # Trigger revolt
            size_seed = generate_seed(
                game_id,
                current_day,
                current_part,
                f"raise_army_revolt_size:{hex_id}:{commander_id}",
            )
            revolt_size = roll_dice(size_seed, "1d20")["total"] * 500
            raise ValueError(
                f"Revolt triggered in hex {hex_id}! Army of {revolt_size} infantry rebels."
            )

    # Update last recruited day
    hex_obj.last_recruited_day = current_day

    # Calculate total infantry first to determine noncombatant count
    total_infantry = sum(
        item["soldier_count"] for item in composition if "infantry" in item.get("type", "").lower()
    )

    # Calculate initial noncombatant count (25% by default)
    initial_noncombatants = int(total_infantry * 0.25)

    # Create the army
    new_army = Army(
        game_id=game_id,
        commander_id=commander_id,
        current_hex_id=hex_id,
        status="idle",
        morale_current=9,  # Default morale
        morale_resting=9,  # Default resting morale
        morale_max=12,  # Default max morale
        noncombatant_count=initial_noncombatants,
        supplies_current=0,  # Will be calculated based on capacity
        # Other fields will be updated by update_army_composition
    )

    session.add(new_army)
    session.flush()  # Get army ID for detachments

    # Apply commander traits to army attributes
    _apply_commander_traits_to_army(new_army, commander_id, session)

    # Create detachments based on composition
    for i, unit_info in enumerate(composition):
        unit_type_name = unit_info.get("type", "infantry")
        count = unit_info.get("soldier_count", 0)
        wagons = unit_info.get("wagon_count", 0)

        # Query for the actual unit type ID
        unit_type_obj = session.query(UnitType).filter(UnitType.name == unit_type_name).first()
        if not unit_type_obj:
            # If unit type doesn't exist, default to infantry
            unit_type_obj = session.query(UnitType).filter(UnitType.name == "infantry").first()

        detachment = Detachment(
            army_id=new_army.id,
            unit_type_id=unit_type_obj.id
            if unit_type_obj
            else 1,  # Default to first unit type if not found
            name=f"{unit_type_name.title()} Detachment {i + 1}",
            soldier_count=count,
            wagon_count=wagons,
            formation_position=i,
            region_of_origin=f"Hex {hex_id}",
        )

        session.add(detachment)

    # Update the army with calculated values
    update_army_composition(new_army, session)

    # Set initial supplies to a reasonable amount (configurable default)
    new_army.supplies_current = min(
        new_army.supplies_capacity, total_infantry * INITIAL_SUPPLIES_PER_SOLDIER
    )

    session.commit()
    return new_army


def distribute_loot(army: Army, amount_per_soldier: int, session: Session) -> None:
    """Distribute loot to soldiers, granting +1 morale per loot per soldier.

    Args:
        army: The army to distribute loot to
        amount_per_soldier: Amount of loot per soldier
        session: Database session

    Raises:
        ValueError: If insufficient loot
    """
    try:
        total_soldiers = calculate_total_soldiers(army)
        total_loot_needed = total_soldiers * amount_per_soldier

        if army.loot_carried < total_loot_needed:
            raise ValueError(f"Insufficient loot: {army.loot_carried} < {total_loot_needed} needed")

        # Distribute loot (reduces carried loot)
        army.loot_carried -= total_loot_needed

        # Grant morale bonus (+1 per loot per soldier, but rules say +1 total per point)
        morale_bonus = (
            1  # Per rules: +1 morale per loot per soldier (but simplified to +1 if distributed)
        )
        army.morale_current = min(army.morale_max, army.morale_current + morale_bonus)

        session.commit()
    except Exception:
        session.rollback()
        raise


def _apply_commander_traits_to_army(army: Army, commander_id: int, session: Session):
    """Apply commander traits to army attributes during creation.

    Args:
        army: The army to modify
        commander_id: ID of the commander
        session: Database session
    """
    commander = session.get(Commander, commander_id)
    if not commander:
        return

    # Apply Beloved trait: +1 resting morale
    for commander_trait in commander.traits:
        if commander_trait.trait.name.lower() == "beloved":
            army.morale_resting = min(army.morale_max, army.morale_resting + 1)
            # Also set current morale to resting if it was at the old default
            if army.morale_current == DEFAULT_STARTING_MORALE:  # Default starting morale
                army.morale_current = army.morale_resting
            break
