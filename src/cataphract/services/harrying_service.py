"""Harrying Service for Cataphract.

This module provides functions for managing harrying detachments that can
attack enemy armies within scouting range.
"""

from sqlalchemy.orm import Session

from cataphract.models import Army, Detachment
from cataphract.services.visibility_service import VisibilityService
from cataphract.utils.rng import generate_seed, roll_dice


class HarryingService:
    """Service for handling harrying mechanics in Cataphract."""

    def __init__(self, session: Session, visibility: VisibilityService):
        self.session = session
        self.visibility = visibility

    def can_harry_army(
        self, harrying_detachment: Detachment, target_army: Army, weather: str = "clear"
    ) -> bool:
        """Check if a detachment can harry a target army.

        Args:
            harrying_detachment: The detachment attempting to harry
            target_army: The army to be harried
            weather: Current weather (affects visibility)

        Returns:
            True if detachment can harry the army, False otherwise
        """
        # Get the army that contains the detachment
        detachment_army = harrying_detachment.army

        if not detachment_army or not detachment_army.commander:
            return False

        # Check if target army is in garrison (cannot harry garrisoned armies)
        if target_army.status == "garrisoned":
            return False

        # Check if target army is visible to the commander
        # (within scouting range)
        visible_armies = self.visibility.get_visible_armies(
            detachment_army.commander, weather=weather
        )

        # Check if target army is in the list of visible armies
        return target_army.id in [army.id for army in visible_armies]

    def harry_army(
        self,
        harrying_detachment: Detachment,
        target_army: Army,
        objective: str,
        weather: str = "clear",
    ) -> dict:
        """Execute a harrying action against an enemy army.

        Args:
            harrying_detachment: The detachment performing the harrying
            target_army: The army to be harried
            objective: "kill", "torch", or "steal"
            weather: Current weather (affects success chance)

        Returns:
            Dictionary with harrying results
        """
        result = self._create_harry_result_template(harrying_detachment, target_army, objective)

        # Validate harrying attempt
        validation_result = self._validate_harrying_attempt(
            harrying_detachment, target_army, objective, weather
        )
        if not validation_result["valid"]:
            result["result_description"] = validation_result["error"]
            return result

        # Calculate harrying bonus and attempt success
        bonus = self._calculate_harrying_bonus(harrying_detachment)
        success_result = self._attempt_harry_success(harrying_detachment, target_army, bonus)
        result.update(success_result)

        if result["success"]:
            # Apply successful harrying effects
            damage_result = self._apply_successful_harry(
                harrying_detachment, target_army, objective, bonus
            )
            result.update(damage_result)
            self._apply_harried_status(target_army, harrying_detachment)
        else:
            # Apply failed harrying consequences
            losses = self._apply_harrying_failure(harrying_detachment)
            result["losses"] = losses
            result["result_description"] = (
                f"Harrying failed, harrying detachment took {losses} casualties"
            )

        return result

    def _create_harry_result_template(
        self, harrying_detachment: Detachment, target_army: Army, objective: str
    ) -> dict:
        """Create a template result dictionary for harrying actions."""
        return {
            "success": False,
            "objective": objective,
            "damage_dealt": 0,
            "losses": 0,
            "harrying_detachment_id": harrying_detachment.id,
            "target_army_id": target_army.id,
            "result_description": "",
            "events": [],
        }

    def _validate_harrying_attempt(
        self, harrying_detachment: Detachment, target_army: Army, objective: str, weather: str
    ) -> dict:
        """Validate if a harrying attempt can proceed."""
        # Validate objective
        if objective not in ["kill", "torch", "steal"]:
            return {
                "valid": False,
                "error": "Invalid objective. Must be 'kill', 'torch', or 'steal'",
            }

        # Check if the detachment can harry the target army
        if not self.can_harry_army(harrying_detachment, target_army, weather):
            return {"valid": False, "error": "Target army not within harrying range"}

        return {"valid": True, "error": None}

    def _calculate_harrying_bonus(self, harrying_detachment: Detachment) -> int:
        """Calculate the harrying bonus for a detachment based on unit type."""
        bonus = 0
        if harrying_detachment.unit_type.name.lower() == "skirmisher":
            bonus = 1  # Skirmishers get +1 bonus
        elif harrying_detachment.unit_type.category == "cavalry":
            bonus = 2  # Cavalry get +2 bonus
        elif (
            harrying_detachment.unit_type.special_abilities
            and "harrying_bonus" in harrying_detachment.unit_type.special_abilities
        ):
            bonus = harrying_detachment.unit_type.special_abilities["harrying_bonus"]

        # Cap the bonus at 4
        return min(bonus, 4)

    def _attempt_harry_success(
        self, harrying_detachment: Detachment, target_army: Army, bonus: int
    ) -> dict:
        """Attempt the harrying success roll."""
        seed = generate_seed(
            harrying_detachment.army.id,
            harrying_detachment.army.game.current_day,
            harrying_detachment.army.game.current_day_part,
            f"harry_success_{target_army.id}",
        )
        roll_result = roll_dice(seed, "1d6")
        roll = roll_result["total"]
        success_threshold = min(6, 2 + bonus)

        return {
            "success": roll <= success_threshold,
            "roll": roll,
            "seed": seed,
            "success_threshold": success_threshold,
        }

    def _apply_successful_harry(
        self, harrying_detachment: Detachment, target_army: Army, objective: str, bonus: int
    ) -> dict:
        """Apply the effects of a successful harrying action."""
        result = {"damage_dealt": 0, "result_description": ""}

        if objective == "kill":
            # Kill 20% of harrying detachment size casualties inflicted
            casualties = int(harrying_detachment.soldier_count * 0.20)
            target_army.supplies_current = max(0, target_army.supplies_current - casualties)
            result["damage_dealt"] = casualties
            result["result_description"] = f"Killed {casualties} soldiers in target army"

        elif objective == "torch":
            # (2d6 + bonus) * harrying detachment size supplies destroyed
            torch_seed = generate_seed(
                harrying_detachment.army.id,
                harrying_detachment.army.game.current_day,
                harrying_detachment.army.game.current_day_part,
                f"harry_torch_{target_army.id}",
            )
            torch_result = roll_dice(torch_seed, "2d6")
            d6_roll = torch_result["total"]
            supplies_destroyed = (d6_roll + bonus) * harrying_detachment.soldier_count
            target_army.supplies_current = max(0, target_army.supplies_current - supplies_destroyed)
            result["damage_dealt"] = supplies_destroyed
            result["result_description"] = (
                f"Torching destroyed {supplies_destroyed} supplies in target army"
            )

        elif objective == "steal":
            # (1d6 + bonus) * harrying detachment size loot/supplies captured
            stolen_amount = self._calculate_steal_amount(harrying_detachment, target_army, bonus)
            target_army.supplies_current -= stolen_amount
            harrying_detachment.army.supplies_current = min(
                harrying_detachment.army.supplies_capacity,
                harrying_detachment.army.supplies_current + stolen_amount,
            )
            result["damage_dealt"] = stolen_amount
            result["result_description"] = f"Stole {stolen_amount} supplies from target army"

        return result

    def _calculate_steal_amount(
        self, harrying_detachment: Detachment, target_army: Army, bonus: int
    ) -> int:
        """Calculate the amount of supplies stolen from target army."""
        steal_seed = generate_seed(
            harrying_detachment.army.id,
            harrying_detachment.army.game.current_day,
            harrying_detachment.army.game.current_day_part,
            f"harry_steal_{target_army.id}",
        )
        steal_result = roll_dice(steal_seed, "1d6")
        d6_roll = steal_result["total"]
        stolen_amount = (d6_roll + bonus) * harrying_detachment.soldier_count

        # Can't steal more than target has
        return min(stolen_amount, target_army.supplies_current)

    def _apply_harried_status(self, target_army: Army, harrying_detachment: Detachment) -> None:
        """Apply harried status to target army."""
        if target_army.status_effects is None:
            target_army.status_effects = {}
        target_army.status_effects["harried"] = {  # type: ignore[index]
            "until_day": target_army.game.current_day + 1,  # Effect lasts until next day
            "by_detachment_id": harrying_detachment.id,
        }

    def _apply_harrying_failure(self, harrying_detachment: Detachment) -> int:
        """Apply consequences of failed harrying to the detachment."""
        losses = int(harrying_detachment.soldier_count * 0.20)
        harrying_detachment.soldier_count = max(1, harrying_detachment.soldier_count - losses)
        return losses

    def get_harrying_targets(self, detachment: Detachment, weather: str = "clear") -> list[Army]:
        """Get all armies that can be harried by a detachment.

        Args:
            detachment: The detachment that might harry
            weather: Current weather (affects visibility)

        Returns:
            List of armies that can be harried by this detachment
        """
        army = detachment.army
        if not army or not army.commander:
            return []

        # Get all armies visible to the commander
        visible_armies = self.visibility.get_visible_armies(army.commander, weather=weather)

        # Filter out garrisoned armies (can't harry these)
        return [
            a
            for a in visible_armies
            if a.id != army.id and a.status != "garrisoned"  # Can't harry own army
        ]

    def apply_harried_effects(self, army: Army) -> dict:
        """Apply effects of being harried to an army.

        Args:
            army: The army that is harried

        Returns:
            Dictionary with effect details
        """
        result = {"effects_applied": [], "speed_reduction": 0, "can_rest": True}

        if army.status_effects and army.status_effects.get("harried"):
            # Harried armies move at half speed
            result["speed_reduction"] = 0.5  # This would be used in movement calculations
            result["effects_applied"].append("half_speed")

            # Harried armies cannot rest
            result["can_rest"] = False
            result["effects_applied"].append("cannot_rest")

        return result
