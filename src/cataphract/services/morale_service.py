"""Morale Service for Cataphract.

This module provides functions for managing army morale, including morale checks
with all consequences as specified in the Cataphract rules.
"""

from sqlalchemy.orm import Session

from cataphract.domain.morale import roll_morale_check
from cataphract.domain.morale_data import MoraleConsequenceResult, MoraleConsequenceType
from cataphract.models import Army
from cataphract.utils.rng import generate_seed, random_choice, roll_dice

# Morale consequence constants
MUTINY_CHANCE = 19  # 19-in-20 chance per detachment
ARMY_SPLIT_CHANCE = 3  # 3-in-6 chance per detachment
DESERTION_LOSS_MINOR = 0.10  # 10% casualties
DESERTION_LOSS_MAJOR = 0.20  # 20% casualties
DESERTION_LOSS_MASS = 0.30  # 30% casualties
DESERTION_LOSS_TEMPORARY = 0.05  # 5% casualties for temporary departure
CAMP_FOLLOWER_LOSS = 0.02  # 2% casualties for camp followers
DAYS_PER_WEEK = 7  # Days in a week for morale recovery


class MoraleService:
    """Service for handling morale mechanics in Cataphract."""

    def __init__(self, session: Session):
        self.session = session

    def check_morale(self, army: Army) -> tuple[bool, str, int]:
        """Perform a morale check for an army.

        Args:
            army: The army to check morale for

        Returns:
            Tuple of (success, consequence_type, roll_value)
        """
        seed = generate_seed(
            army.id, army.game.current_day, army.game.current_day_part, "morale_check"
        )
        success, roll = roll_morale_check(army.morale_current, seed)

        if success:
            return True, "army_holds", roll
        # Failure - use roll to determine consequence
        consequence = self._get_consequence_from_roll(roll)
        return False, consequence, roll

    def _get_consequence_from_roll(self, roll: int) -> str:
        """Get consequence type from morale check roll.

        Args:
            roll: The 2d6 roll result

        Returns:
            Consequence type string
        """
        consequence_map = {
            2: "mutiny",
            3: "mass_desertion",
            4: "detachments_defect",
            5: "major_desertion",
            6: "army_splits",
            7: "random_detachment_defects",
            8: "desertion",
            9: "detachments_depart_2d6_days",
            10: "camp_followers",  # Extra 5% noncombatants
            11: "random_detachment_depart_2d6_days",
            12: "no_consequences",
        }
        return consequence_map.get(roll, "no_consequences")

    def apply_consequence(self, army: Army, consequence: str) -> dict:
        """Apply the consequence of a failed morale check to an army.

        Args:
            army: The army to apply consequence to
            consequence: The consequence type

        Returns:
            Dictionary with details of what happened
        """
        # Map consequence strings to handler methods
        consequence_handlers = {
            "mutiny": self._handle_mutiny,
            "mass_desertion": self._handle_mass_desertion,
            "detachments_defect": self._handle_detachment_defect,
            "major_desertion": self._handle_major_desertion,
            "army_splits": self._handle_army_split,
            "random_detachment_defects": self._handle_detachment_defect,  # Same as detachments_defect
            "desertion": self._handle_minor_desertion,
            "detachments_depart_2d6_days": self._handle_temporary_departure,
            "camp_followers": self._handle_camp_followers_desert,
            "random_detachment_depart_2d6_days": self._handle_temporary_departure,  # Same as temporary
            "no_consequences": self._handle_no_consequence,
        }

        handler = consequence_handlers.get(consequence, self._handle_no_consequence)
        result = handler(army) if consequence != "no_consequences" else handler()

        return {
            "consequence": consequence,
            "applied": result.applied,
            "details": result.details,
            "message": result.message,
        }

    # Helper methods for handling different consequences
    def _handle_mutiny(self, army: Army) -> MoraleConsequenceResult:
        """Handle mutiny consequence."""
        detachments_to_mutiny = []
        for idx, det in enumerate(army.detachments):
            seed = generate_seed(
                army.id,
                army.game.current_day,
                army.game.current_day_part,
                f"mutiny_det_{det.id}_{idx}",
            )
            dice_result = roll_dice(seed, "1d20")
            if dice_result["total"] <= MUTINY_CHANCE:  # 19 in 20 chance
                detachments_to_mutiny.append(det.id)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.MUTINY,
            applied=True,
            details={"mutinous_detachments": detachments_to_mutiny},
            message=f"{len(detachments_to_mutiny)}/{len(army.detachments)} detachments mutinied",
        )

    def _handle_mass_desertion(self, army: Army) -> MoraleConsequenceResult:
        """Handle mass desertion consequence."""
        size_reduction = int(army.daily_supply_consumption * DESERTION_LOSS_MASS)
        army.supplies_current = max(0, army.supplies_current - size_reduction)
        army.supplies_capacity = max(0, army.supplies_capacity - size_reduction)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.MASS_DESERTION,
            applied=True,
            details={"size_reduction": size_reduction},
            message="Mass desertion reduced army by 30%",
        )

    def _handle_detachment_defect(self, army: Army) -> MoraleConsequenceResult:
        """Handle detachment defection consequence."""
        # 1d6 random detachments defect to another army
        seed = generate_seed(
            army.id,
            army.game.current_day,
            army.game.current_day_part,
            "detachment_defect_count",
        )
        dice_result = roll_dice(seed, "1d6")
        num_defecting = dice_result["total"]

        defecting_detachments = []
        if army.detachments:
            remaining_detachments = list(army.detachments)
            for i in range(min(num_defecting, len(remaining_detachments))):
                # Randomly select a detachment to defect
                if remaining_detachments:
                    choice_seed = generate_seed(
                        army.id,
                        army.game.current_day,
                        army.game.current_day_part,
                        f"defect_choice_{i}",
                    )
                    choice_result = random_choice(choice_seed, remaining_detachments)
                    defecting_det = choice_result["choice"]
                    defecting_detachments.append(defecting_det.id)
                    remaining_detachments.remove(defecting_det)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.DEFECT,
            applied=True,
            details={"defecting_detachments": defecting_detachments},
            message=f"{len(defecting_detachments)} detachments defected",
        )

    def _handle_major_desertion(self, army: Army) -> MoraleConsequenceResult:
        """Handle major desertion consequence."""
        size_reduction = int(army.daily_supply_consumption * DESERTION_LOSS_MAJOR)
        army.supplies_current = max(0, army.supplies_current - size_reduction)
        army.supplies_capacity = max(0, army.supplies_capacity - size_reduction)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.MAJOR_DESERTION,
            applied=True,
            details={"size_reduction": size_reduction},
            message="Major desertion reduced army by 20%",
        )

    def _handle_army_split(self, army: Army) -> MoraleConsequenceResult:
        """Handle army split consequence."""
        detachments_to_split = []
        for idx, det in enumerate(army.detachments):
            seed = generate_seed(
                army.id,
                army.game.current_day,
                army.game.current_day_part,
                f"split_det_{det.id}_{idx}",
            )
            dice_result = roll_dice(seed, "1d6")
            if dice_result["total"] <= ARMY_SPLIT_CHANCE:  # 3 in 6 chance
                detachments_to_split.append(det.id)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.SPLIT,
            applied=True,
            details={"splitting_detachments": detachments_to_split},
            message=f"{len(detachments_to_split)}/{len(army.detachments)} detachments split to form new army",
        )

    def _handle_minor_desertion(self, army: Army) -> MoraleConsequenceResult:
        """Handle minor desertion consequence."""
        size_reduction = int(army.daily_supply_consumption * DESERTION_LOSS_MINOR)
        army.supplies_current = max(0, army.supplies_current - size_reduction)
        army.supplies_capacity = max(0, army.supplies_capacity - size_reduction)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.MINOR_DESERTION,
            applied=True,
            details={"size_reduction": size_reduction},
            message="Minor desertion reduced army by 10%",
        )

    def _handle_camp_followers_desert(self, army: Army) -> MoraleConsequenceResult:
        """Handle camp followers desertion consequence."""
        size_reduction = int(army.daily_supply_consumption * CAMP_FOLLOWER_LOSS)
        army.supplies_current = max(0, army.supplies_current - size_reduction)
        army.supplies_capacity = max(0, army.supplies_capacity - size_reduction)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.CAMP_FOLLOWERS,
            applied=True,
            details={"size_reduction": size_reduction},
            message="Camp followers deserted, reducing army supplies",
        )

    def _handle_temporary_departure(self, army: Army) -> MoraleConsequenceResult:
        """Handle temporary departure consequence."""
        size_reduction = int(army.daily_supply_consumption * DESERTION_LOSS_TEMPORARY)
        army.supplies_current = max(0, army.supplies_current - size_reduction)
        army.supplies_capacity = max(0, army.supplies_capacity - size_reduction)

        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.TEMPORARY_DEPARTURE,
            applied=True,
            details={"size_reduction": size_reduction},
            message="Some units temporarily departed, reducing army size",
        )

    def _handle_no_consequence(self) -> MoraleConsequenceResult:
        """Handle no consequence case."""
        return MoraleConsequenceResult(
            consequence_type=MoraleConsequenceType.NO_CONSEQUENCE,
            applied=True,
            details={},
            message="No consequences from morale check",
        )

    def handle_army_rout(self, army: Army) -> dict:
        """Handle an army routing after a battle or morale failure.

        Args:
            army: The routing army

        Returns:
            Dictionary with details of the routing
        """
        result = {"army_id": army.id, "supplies_lost": 0, "retreat_hexes": 0, "status": "routed"}

        # Lose 1d6 * 10% of supplies
        supply_seed = generate_seed(
            army.id, army.game.current_day, army.game.current_day_part, "rout_supply_loss"
        )
        dice_result = roll_dice(supply_seed, "1d6")
        supply_percentage_lost = dice_result["total"] * 10
        supplies_lost = int(army.supplies_current * supply_percentage_lost / 100)
        army.supplies_current = max(0, army.supplies_current - supplies_lost)
        result["supplies_lost"] = supplies_lost

        # Army retreats a further 1d6 hexes away (as much time as that takes) out of control
        retreat_seed = generate_seed(
            army.id, army.game.current_day, army.game.current_day_part, "rout_retreat_distance"
        )
        dice_result = roll_dice(retreat_seed, "1d6")
        retreat_hexes = dice_result["total"]
        result["retreat_hexes"] = retreat_hexes

        # Change army status to routed
        army.status = "routed"

        # The morale check consequence table doesn't directly cause routing;
        # it's a battle result. We'll return the routing info for the caller to handle.
        return result

    def update_army_morale(self, army: Army, change: int):
        """Update an army's morale by the specified amount.

        Args:
            army: The army to update
            change: Amount to change morale (positive or negative)
        """
        new_morale = army.morale_current + change

        # Morale should be between 0 and the army's maximum (default 12)
        army.morale_current = max(0, min(army.morale_max, new_morale))

    def reset_army_morale_towards_resting(self, army: Army, days_resting: int = 1):
        """Reset army morale towards resting morale by 1 per week.

        Args:
            army: The army to update
            days_resting: Number of days of rest (affects how much morale recovers)
        """
        # Morale adjusts 1/week toward resting morale
        # Only adjust if current morale is not already at or above resting
        if army.morale_current < army.morale_resting and days_resting >= DAYS_PER_WEEK:
            # If resting for a full week, adjust by 1
            army.morale_current = min(army.morale_resting, army.morale_current + 1)
        elif army.morale_current > army.morale_resting and days_resting >= DAYS_PER_WEEK:
            # If current morale is above resting, decrease toward resting
            army.morale_current = max(army.morale_resting, army.morale_current - 1)
