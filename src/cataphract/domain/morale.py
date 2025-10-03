"""Morale domain logic for Cataphract.

This module contains pure functions for morale calculations and checks.
"""

from enum import Enum
from typing import Any

from cataphract.models.army import Army
from cataphract.models.commander import Trait
from cataphract.utils.rng import check_success, random_choice, roll_dice


class MoraleConsequence(Enum):
    """Morale failure consequences per rules."""

    MUTINY = 2  # 19/20 detachments defect
    MASS_DESERTION = 3  # 30% loss
    DETACHMENTS_DEFECT = 4  # 1d6 detachments defect
    MAJOR_DESERTION = 5  # 20% loss
    ARMY_SPLITS = 6  # 3/6 detachments to new commander
    RANDOM_DETACHMENT_DEFECTS = 7
    DESERTION = 8  # 10% loss
    DETACHMENTS_DEPART = 9  # 1d6 detachments depart 2d6 days
    CAMP_FOLLOWERS = 10  # +5% noncombatants
    DETACHMENT_DEPARTS = 11  # 1 detachment departs 2d6 days
    NO_CONSEQUENCES = 12


def roll_morale_check(morale: int, seed: str) -> tuple[bool, int]:
    """Roll 2d6 morale check: success if <= morale.

    Args:
        morale: Current morale (2-12)
        seed: Deterministic seed for RNG

    Returns:
        (success: bool, roll: int)
    """
    result = roll_dice(seed, "2d6")
    roll_value = result["total"]
    success = roll_value <= morale
    return success, roll_value


def apply_morale_consequence(  # noqa: PLR0912, PLR0915
    army: Army, roll: int, traits: list[Trait], seed: str, current_day: int = 0
) -> dict[str, Any]:
    """Apply morale failure consequence based on roll.

    Modifies army in place. Poet trait adds +2 to roll for less severe consequences.

    Args:
        army: The army failing morale
        roll: The 2d6 roll result
        traits: Commander traits
        seed: Deterministic seed for RNG
        current_day: Current game day (for departure tracking)

    Returns:
        Dict with consequence details
    """
    # Poet trait: +2 to roll for consequence determination
    has_poet = any(getattr(t, "name", "").lower() == "poet" for t in traits)
    effective_roll_raw = roll + 2 if has_poet else roll
    effective_roll = max(2, min(12, effective_roll_raw))

    consequence = MoraleConsequence(effective_roll)

    details = {"consequence_type": consequence.name, "roll": roll}

    match consequence:
        case MoraleConsequence.MUTINY:
            # 19/20 chance each detachment defects
            defect_chance = 19 / 20
            defecting = []
            for i, det in enumerate(army.detachments):
                check_result = check_success(f"{seed}:mutiny_det_{i}", defect_chance, "1d20")
                if check_result["success"]:
                    defecting.append(det)
                    det.army_id = None  # Mark as defected (service handles reassignment)
            details["defecting_detachments"] = len(defecting)

        case MoraleConsequence.MASS_DESERTION:
            loss_pct = 0.30
            # Reduce soldiers proportionally across detachments
            for det in army.detachments:
                det.soldier_count = max(1, int(det.soldier_count * (1 - loss_pct)))
            army.supplies_current = int(army.supplies_current * (1 - loss_pct))
            details["loss_percentage"] = loss_pct

        case MoraleConsequence.DETACHMENTS_DEFECT:
            # 1d6 random detachments defect to another army
            num_defecting = roll_dice(f"{seed}:defect_count", "1d6")["total"]
            # Leave at least 1 detachment
            num_defecting = min(num_defecting, max(0, len(army.detachments) - 1))
            if num_defecting > 0:
                # Select random detachments
                choice_result = random_choice(
                    f"{seed}:defect_selection", list(range(len(army.detachments)))
                )
                selected_indices = [choice_result["index"]]
                # Get remaining indices for additional selections
                for i in range(1, num_defecting):
                    remaining = [
                        j for j in range(len(army.detachments)) if j not in selected_indices
                    ]
                    if remaining:
                        choice_result = random_choice(f"{seed}:defect_selection_{i}", remaining)
                        selected_indices.append(choice_result["index"])

                defecting = [army.detachments[idx] for idx in selected_indices]
                for det in defecting:
                    det.army_id = None  # Mark as defected
                details["defecting_detachments"] = len(defecting)

        case MoraleConsequence.MAJOR_DESERTION:
            loss_pct = 0.20
            # Reduce soldiers proportionally across detachments
            for det in army.detachments:
                det.soldier_count = max(1, int(det.soldier_count * (1 - loss_pct)))
            army.supplies_current = int(army.supplies_current * (1 - loss_pct))
            details["loss_percentage"] = loss_pct

        case MoraleConsequence.ARMY_SPLITS:
            # 3-in-6 chance each detachment joins a new commander
            split_chance = 3 / 6
            splitting = []
            for i, det in enumerate(army.detachments):
                check_result = check_success(f"{seed}:split_det_{i}", split_chance, "1d6")
                if check_result["success"]:
                    splitting.append(det)

            # Leave at least one detachment
            if len(splitting) >= len(army.detachments):
                splitting = splitting[:-1]

            for det in splitting:
                det.army_id = None  # Mark as splitting off
            details["splitting_detachments"] = len(splitting)

        case MoraleConsequence.RANDOM_DETACHMENT_DEFECTS:
            # One random detachment defects
            if len(army.detachments) > 1:
                choice_result = random_choice(
                    f"{seed}:single_defect", list(range(len(army.detachments)))
                )
                defecting_det = army.detachments[choice_result["index"]]
                defecting_det.army_id = None
                details["defecting_detachments"] = 1
            else:
                details["defecting_detachments"] = 0

        case MoraleConsequence.DESERTION:
            loss_pct = 0.10
            # Reduce soldiers proportionally across detachments
            for det in army.detachments:
                det.soldier_count = max(1, int(det.soldier_count * (1 - loss_pct)))
            army.supplies_current = int(army.supplies_current * (1 - loss_pct))
            details["loss_percentage"] = loss_pct

        case MoraleConsequence.DETACHMENTS_DEPART:
            # 1d6 detachments depart for 2d6 days
            num_departing = roll_dice(f"{seed}:depart_count", "1d6")["total"]
            days_gone = roll_dice(f"{seed}:depart_days", "2d6")["total"]
            # Leave at least 1 detachment
            num_departing = min(num_departing, max(0, len(army.detachments) - 1))

            if num_departing > 0:
                # Select random detachments
                choice_result = random_choice(
                    f"{seed}:depart_selection", list(range(len(army.detachments)))
                )
                selected_indices = [choice_result["index"]]
                # Get remaining indices for additional selections
                for i in range(1, num_departing):
                    remaining = [
                        j for j in range(len(army.detachments)) if j not in selected_indices
                    ]
                    if remaining:
                        choice_result = random_choice(f"{seed}:depart_selection_{i}", remaining)
                        selected_indices.append(choice_result["index"])

                departing = [army.detachments[idx] for idx in selected_indices]

                # Store in army.status_effects
                if army.status_effects is None:
                    army.status_effects = {}
                army.status_effects["departed_detachments"] = {  # type: ignore[index]
                    "detachment_ids": [det.id for det in departing],
                    "return_day": current_day + days_gone,
                }
                details["departing_detachments"] = num_departing
                details["return_in_days"] = days_gone

        case MoraleConsequence.CAMP_FOLLOWERS:
            # +5% noncombatants
            increase = int(army.noncombatant_count * 0.05)
            army.noncombatant_count = army.noncombatant_count + increase
            details["noncombatant_increase"] = increase

        case MoraleConsequence.DETACHMENT_DEPARTS:
            # 1 detachment departs for 2d6 days
            days_gone = roll_dice(f"{seed}:single_depart_days", "2d6")["total"]

            if len(army.detachments) > 1:
                # Select random detachment
                choice_result = random_choice(
                    f"{seed}:single_depart_selection", list(range(len(army.detachments)))
                )
                departing_det = army.detachments[choice_result["index"]]

                # Store in army.status_effects
                if army.status_effects is None:
                    army.status_effects = {}
                army.status_effects["departed_detachments"] = {  # type: ignore[index]
                    "detachment_ids": [departing_det.id],
                    "return_day": current_day + days_gone,
                }
                details["departing_detachments"] = 1
                details["return_in_days"] = days_gone
            else:
                details["departing_detachments"] = 0

        case MoraleConsequence.NO_CONSEQUENCES:
            pass

        case _:
            # Default handling for unhandled (should not occur)
            details["unhandled"] = True

    # Veteran: Never routs
    has_veteran = any(getattr(t, "name", "").lower() == "veteran" for t in traits)
    if has_veteran and consequence in [MoraleConsequence.ARMY_SPLITS, MoraleConsequence.MUTINY]:
        details["veteran_prevented_rout"] = True
        # Prevent full rout

    return details


def adjust_morale(army: Army, change: int, max_morale: int = 12) -> None:
    """Adjust army morale by change amount, capped at max."""
    army.morale_current = max(
        2, min(max_morale, army.morale_current + change)
    )  # Min 2 to avoid immediate failure
