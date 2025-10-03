"""Supply Logistics Service for Cataphract.

This module provides functions for managing supplies, including foraging,
torching, supply consumption, and logistics management.
"""

from sqlalchemy.orm import Session

from cataphract.domain.morale_data import (
    ForageParameters,
    ForageResult,
    TorchParameters,
    TorchResult,
)
from cataphract.domain.supply import detachment_has_ability
from cataphract.models import Army, Hex
from cataphract.services.visibility_service import VisibilityService
from cataphract.utils.hex_math import HexCoord, hex_distance, hexes_in_range
from cataphract.utils.rng import generate_seed, roll_dice

# Supply constants
FORAGING_REVOLT_CHANCE_SECOND_TIME = 2  # in 6 chance for second foraging
TORCHING_REVOLT_CHANCE = 2  # in 6 chance for torching
DAYS_PER_YEAR = 365  # days in a year
DAYS_UNTIL_STARVATION = 90  # days until army dissolves without supplies (unused)
DAYS_UNTIL_DISSOLUTION = 14  # days without supplies before army dissolves (two weeks)
RECENTLY_CONQUERED_THRESHOLD = 90  # days for territory to be considered recently conquered
CAVALRY_FORAGING_RANGE = 2  # hex range for cavalry foraging
BASE_REVOLT_CHANCE = 2  # base revolt chance in 6
SCOUTING_RANGE_REDUCTION_BAD_WEATHER = 2  # hex reduction for bad weather


class SupplyService:
    """Service for handling supply logistics in Cataphract."""

    def __init__(self, session: Session, visibility: VisibilityService):
        self.session = session
        self.visibility = visibility

    def forage(self, params: ForageParameters) -> ForageResult:
        """Allow an army to forage supplies from nearby hexes.

        Args:
            params: ForageParameters containing all necessary information

        Returns:
            ForageResult with foraging outcomes
        """
        foraging_range = self._calculate_foraging_range(params.army, params.weather)
        current_hex = self.session.get(Hex, params.army.current_hex_id)

        if not current_hex:
            return ForageResult(
                success=False,
                foraged_supplies=0,
                foraged_hexes=[],
                failed_hexes=[],
                events=["Army location not found"],
            )

        foraged_hexes, failed_hexes, events = [], [], []
        total_supplies = 0
        revolt_occurred = False

        for hex_id in params.target_hexes:
            hex_result = self._forage_single_hex(params.army, hex_id, current_hex, foraging_range)

            if hex_result["success"]:
                foraged_hexes.append(hex_id)
                total_supplies += hex_result["supplies_gained"]
                if hex_result["revolt_triggered"]:
                    revolt_occurred = True
            else:
                failed_hexes.append({"hex_id": hex_id, "reason": hex_result["reason"]})

            events.extend(hex_result["events"])

        return ForageResult(
            success=len(foraged_hexes) > 0,
            foraged_supplies=total_supplies,
            foraged_hexes=foraged_hexes,
            failed_hexes=failed_hexes,
            events=events,
            revolt_occurred=revolt_occurred,
        )

    def _calculate_foraging_range(self, army: Army, weather: str) -> int:
        """Calculate the effective foraging range for an army."""
        foraging_range = 1  # Base range

        # Check if army has cavalry (increases foraging range to 2)
        for detachment in army.detachments:
            if detachment.unit_type.category == "cavalry" or detachment_has_ability(
                detachment, "acts_as_cavalry_for_foraging"
            ):
                foraging_range = CAVALRY_FORAGING_RANGE
                break

        # Check for Outrider trait (with cavalry, 3-hex foraging)
        if army.commander:
            for trait in army.commander.traits:
                if (
                    trait.trait.name.lower() == "outrider"
                    and foraging_range >= CAVALRY_FORAGING_RANGE
                ):
                    foraging_range = 3
                    break

        # Bad weather reduces range
        if weather in ["bad", "storm"]:
            foraging_range -= 1
        elif weather == "very_bad":
            foraging_range -= SCOUTING_RANGE_REDUCTION_BAD_WEATHER

        # Ranger trait: Ignore weather penalties to foraging range
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "ranger":
                    if weather in ["bad", "storm"]:
                        foraging_range += 1
                    elif weather == "very_bad":
                        foraging_range += SCOUTING_RANGE_REDUCTION_BAD_WEATHER
                    break

        return max(0, foraging_range)

    def _forage_single_hex(
        self, army: Army, hex_id: int, current_hex: Hex, foraging_range: int
    ) -> dict:
        """Process foraging for a single hex."""
        target_hex = self.session.get(Hex, hex_id)
        if not target_hex:
            return {"success": False, "reason": "Hex not found", "events": []}

        # Check distance
        army_coord = HexCoord(q=current_hex.q, r=current_hex.r)
        target_coord = HexCoord(q=target_hex.q, r=target_hex.r)
        distance = hex_distance(army_coord, target_coord)

        if distance > foraging_range:
            return {
                "success": False,
                "reason": f"Hex too far (distance: {distance}, max: {foraging_range})",
                "events": [],
            }

        # Check if hex can be foraged
        if target_hex.foraging_times_remaining <= 0:
            return {
                "success": False,
                "reason": "Hex has been foraged too many times this season",
                "events": [],
            }

        if target_hex.settlement_score <= 0:
            return {"success": False, "reason": "Hex has no settlement value", "events": []}

        # Process foraging with revolt check
        revolt_triggered = self._check_and_trigger_revolt(army, target_hex, "forage")
        supplies_gained = self._calculate_foraged_supplies(army, target_hex)

        # Update hex and army
        target_hex.foraging_times_remaining -= 1
        target_hex.last_foraged_day = army.game.current_day
        army.supplies_current = min(army.supplies_capacity, army.supplies_current + supplies_gained)

        events = []
        if revolt_triggered:
            events.append(f"Revolt triggered in hex {hex_id}")

        return {
            "success": True,
            "supplies_gained": supplies_gained,
            "revolt_triggered": revolt_triggered,
            "events": events,
        }

    def _check_and_trigger_revolt(self, army: Army, hex_obj: Hex, action_type: str) -> bool:
        """Check if revolt should occur and trigger it if needed."""
        if action_type == "forage":
            last_action_day = hex_obj.last_foraged_day
        else:  # torch
            last_action_day = hex_obj.last_torched_day

        should_check_revolt = (
            last_action_day and (army.game.current_day - last_action_day) <= DAYS_PER_YEAR
        )

        if not should_check_revolt:
            return False

        # Determine revolt chance
        territory_type = self._get_territory_type(hex_obj, army)
        revolt_chance = (
            FORAGING_REVOLT_CHANCE_SECOND_TIME
            if action_type == "forage"
            else TORCHING_REVOLT_CHANCE
        )

        if territory_type == "hostile":
            revolt_chance += 1

        # Check for Honorable trait (reduces revolt chance)
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "honorable":
                    revolt_chance = max(0, revolt_chance - 1)
                    break

        # Roll for revolt
        seed = generate_seed(
            army.game_id,
            army.game.current_day,
            army.game.current_day_part,
            f"{action_type}_revolt_hex_{hex_obj.id}",
        )
        dice_result = roll_dice(seed, "1d6")

        if dice_result["total"] <= revolt_chance:
            self._trigger_revolt(army, hex_obj)
            return True

        return False

    def _calculate_foraged_supplies(self, army: Army, hex_obj: Hex) -> int:
        """Calculate supplies gained from foraging."""
        base_supplies = (hex_obj.settlement_score or 0) * 500

        # Check for Raider trait (10% extra supplies foraged)
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "raider":
                    base_supplies = int(base_supplies * 1.10)
                    break

        return base_supplies

    def torch(self, params: TorchParameters) -> TorchResult:
        """Allow an army to torch hexes, preventing foraging until spring.

        Args:
            params: TorchParameters containing all necessary information

        Returns:
            TorchResult with torching outcomes
        """
        torching_range = self._calculate_torching_range(params.army, params.weather)
        current_hex = self.session.get(Hex, params.army.current_hex_id)

        if not current_hex:
            return TorchResult(
                success=False, torched_hexes=[], failed_hexes=[], events=["Army location not found"]
            )

        torched_hexes, failed_hexes, events = [], [], []
        revolt_occurred = False

        for hex_id in params.target_hexes:
            hex_result = self._torch_single_hex(params.army, hex_id, current_hex, torching_range)

            if hex_result["success"]:
                torched_hexes.append(hex_id)
                if hex_result["revolt_triggered"]:
                    revolt_occurred = True
            else:
                failed_hexes.append({"hex_id": hex_id, "reason": hex_result["reason"]})

            events.extend(hex_result["events"])

        return TorchResult(
            success=len(torched_hexes) > 0,
            torched_hexes=torched_hexes,
            failed_hexes=failed_hexes,
            events=events,
            revolt_occurred=revolt_occurred,
        )

    def _calculate_torching_range(self, army: Army, weather: str) -> int:
        """Calculate the effective torching range for an army."""
        torching_range = 1  # Base range

        # Check if army has cavalry (increases torching range to 2)
        for detachment in army.detachments:
            if detachment.unit_type.category == "cavalry" or detachment_has_ability(
                detachment, "acts_as_cavalry_for_scouting"
            ):
                torching_range = CAVALRY_FORAGING_RANGE
                break

        # Check for Outrider trait (with cavalry, 3-hex torching)
        if army.commander:
            for trait in army.commander.traits:
                if (
                    trait.trait.name.lower() == "outrider"
                    and torching_range >= CAVALRY_FORAGING_RANGE
                ):
                    torching_range = 3
                    break

        # Bad weather reduces range
        if weather in ["bad", "storm"]:
            torching_range -= 1
        elif weather == "very_bad":
            torching_range -= 2

        # Ranger trait: Ignore weather penalties to torching range
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "ranger":
                    if weather in ["bad", "storm"]:
                        torching_range += 1
                    elif weather == "very_bad":
                        torching_range += 2
                    break

        return max(0, torching_range)

    def _torch_single_hex(
        self, army: Army, hex_id: int, current_hex: Hex, torching_range: int
    ) -> dict:
        """Process torching for a single hex."""
        target_hex = self.session.get(Hex, hex_id)
        if not target_hex:
            return {"success": False, "reason": "Hex not found", "events": []}

        # Check distance
        army_coord = HexCoord(q=current_hex.q, r=current_hex.r)
        target_coord = HexCoord(q=target_hex.q, r=target_hex.r)
        distance = hex_distance(army_coord, target_coord)

        if distance > torching_range:
            return {
                "success": False,
                "reason": f"Hex too far (distance: {distance}, max: {torching_range})",
                "events": [],
            }

        # Process torching with revolt check
        revolt_triggered = self._check_and_trigger_revolt(army, target_hex, "torch")
        self._apply_torch_effect(army, target_hex, torching_range)

        events = []
        if revolt_triggered:
            events.append(f"Revolt triggered in hex {hex_id}")

        return {"success": True, "revolt_triggered": revolt_triggered, "events": events}

    def _apply_torch_effect(self, army: Army, target_hex: Hex, torching_range: int) -> list[int]:
        """Apply torch effect to target hex and surrounding area."""
        # Torch the primary hex
        target_hex.is_torched = True
        target_hex.last_torched_day = army.game.current_day

        # Torching affects current + adjacent hexes within scouting range
        center_coord = HexCoord(q=target_hex.q, r=target_hex.r)
        affected_coords = hexes_in_range(center_coord, torching_range)
        affected_hex_ids = []

        for affected_coord in affected_coords:
            affected_hex = (
                self.session.query(Hex)
                .filter(
                    Hex.game_id == target_hex.game_id,
                    Hex.q == affected_coord.q,
                    Hex.r == affected_coord.r,
                )
                .first()
            )

            if affected_hex:
                affected_hex.is_torched = True
                affected_hex.last_torched_day = army.game.current_day
                affected_hex_ids.append(affected_hex.id)

        return affected_hex_ids

    def _get_territory_type(self, hex_obj: Hex, army: Army) -> str:
        """Determine territory classification from army's faction perspective.

        Args:
            hex_obj: The hex to classify
            army: The army doing the action (to determine perspective)

        Returns:
            Territory type: "friendly", "neutral", "hostile", or "recently_conquered"
        """
        if not hex_obj.controlling_faction_id:
            return "neutral"  # No controlling faction

        # Check if hex is controlled by same faction as acting army
        if hex_obj.controlling_faction_id == army.commander.faction_id:
            # Check if "recently conquered" (within 90 days)
            if (
                hasattr(hex_obj, "last_control_change_day")
                and hex_obj.last_control_change_day
                and army.game.current_day - hex_obj.last_control_change_day
                <= RECENTLY_CONQUERED_THRESHOLD
            ):
                return "recently_conquered"
            return "friendly"

        # Check if controlled by allied faction
        # This would normally check faction relations, simplified for now
        return "hostile"  # Assuming non-allied is hostile

    def _trigger_revolt(self, army: Army, hex_obj: Hex) -> dict:
        """Trigger a revolt in a hex.

        Args:
            army: The army that triggered the revolt (for game state)
            hex_obj: The hex where revolt occurs

        Returns:
            Dictionary with revolt details
        """
        # Generate revolt army size: 1d20 * 500 infantry
        seed = generate_seed(
            army.game_id,
            army.game.current_day,
            army.game.current_day_part,
            f"revolt_size_hex_{hex_obj.id}",
        )
        dice_roll = roll_dice(seed, "1d20")  # Using new API that expects (seed, notation)
        dice_result = dice_roll["total"]
        army_size = dice_result * 500

        # In a real implementation, this would create a rebel army
        # For now, we just return the details
        return {
            "hex_id": hex_obj.id,
            "army_size": army_size,
            "event": f"Revolt of {army_size} local troops",
        }

    def consume_supplies(self, army: Army) -> dict:
        """Consume daily supplies for an army.

        Args:
            army: The army to consume supplies for

        Returns:
            Dictionary with consumption results
        """
        result = {
            "consumed": army.daily_supply_consumption,
            "resulting_supplies": 0,
            "starvation_days": 0,
            "army_status": "normal",
        }

        # Subtract daily consumption from current supplies
        army.supplies_current -= army.daily_supply_consumption

        # Check for starvation
        if army.supplies_current <= 0:
            # Army goes into starvation mode
            army.days_without_supplies += 1

            # Lose 1 morale per day without supplies
            army.morale_current = max(0, army.morale_current - 1)

            result["army_status"] = "starving"
            result["starvation_days"] = army.days_without_supplies

            # After 14 days without supplies, army dissolves
            if army.days_without_supplies >= DAYS_UNTIL_DISSOLUTION:
                army.status = "routed"  # In this context, routed means dissolved
                result["army_status"] = "dissolved"
        else:
            # Reset starvation counter
            army.days_without_supplies = 0
            result["army_status"] = "normal"

        result["resulting_supplies"] = max(0, army.supplies_current)

        return result

    def transfer_supplies(
        self, from_army: Army, to_army: Army, amount: int, session: Session
    ) -> dict:
        """Transfer supplies between armies.

        Args:
            from_army: Army to transfer from
            to_army: Army to transfer to
            amount: Amount of supplies to transfer
            session: Database session for committing changes

        Returns:
            Dictionary with transfer results
        """
        result = {"success": False, "transferred": 0, "error": None}

        # Check if armies are in the same hex
        if from_army.current_hex_id != to_army.current_hex_id:
            result["error"] = "Armies must be in the same hex to transfer supplies"
            return result

        # Check if amount is valid
        if amount <= 0:
            result["error"] = "Transfer amount must be positive"
            return result

        # Check if from_army has enough supplies
        if from_army.supplies_current < amount:
            result["error"] = f"Not enough supplies: {from_army.supplies_current} < {amount}"
            return result

        # Check if to_army has enough capacity
        if to_army.supplies_current + amount > to_army.supplies_capacity:
            total = to_army.supplies_current + amount
            result["error"] = f"Not enough capacity: {total} > {to_army.supplies_capacity}"
            return result

        # Perform the transfer
        from_army.supplies_current -= amount
        to_army.supplies_current += amount

        # Commit changes to database
        session.commit()

        result["success"] = True
        result["transferred"] = amount

        return result
