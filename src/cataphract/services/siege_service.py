"""Siege and Assault Service for Cataphract.

This module provides functions for managing sieges, assaults, and stronghold
mechanics according to the Cataphract rules.
"""

from sqlalchemy.orm import Session

from cataphract.models import Army, Siege, Stronghold
from cataphract.services.battle_service import BattleService
from cataphract.services.morale_service import MoraleService
from cataphract.utils.rng import generate_seed, roll_dice


class SiegeService:
    """Service for handling siege and assault mechanics in Cataphract."""

    def __init__(self, session: Session, battle: BattleService, morale: MoraleService):
        self.session = session
        self.battle = battle
        self.morale = morale

    def start_siege(self, attacker_army: Army, stronghold: Stronghold) -> dict:
        """Start a siege of a stronghold.

        Args:
            attacker_army: The army starting the siege
            stronghold: The stronghold being besieged

        Returns:
            Dictionary with siege start results
        """
        result = {"success": False, "siege_id": None, "message": "", "events": []}

        # Check if army is adjacent to the stronghold
        # This would require hex distance calculation, simplified for now
        # Assuming the army is properly positioned

        # Check if stronghold is already under siege
        existing_siege = (
            self.session.query(Siege)
            .filter(Siege.stronghold_id == stronghold.id, Siege.status == "ongoing")
            .first()
        )

        if existing_siege:
            result["message"] = f"Stronghold {stronghold.name} is already under siege"
            return result

        # Calculate initial threshold with Ironsides trait
        initial_threshold = stronghold.base_threshold
        threshold_modifiers = {}

        # Check for Ironsides trait on defender (adds +5 to threshold)
        defender_army_id = None
        if (
            hasattr(stronghold, "garrison")
            and stronghold.garrison
            and hasattr(stronghold.garrison, "id")
        ):
            defender_army_id = stronghold.garrison.id
            defender_army = self.session.get(Army, defender_army_id)
            if defender_army and defender_army.commander:
                has_ironsides = any(
                    t.trait.name.lower() == "ironsides" for t in defender_army.commander.traits
                )
                if has_ironsides:
                    initial_threshold += 5
                    threshold_modifiers["ironsides"] = 5

        # Create new siege
        siege = Siege(
            game_id=attacker_army.game_id,
            stronghold_id=stronghold.id,
            attacker_armies=[attacker_army.id],
            defender_army_id=defender_army_id,
            started_on_day=attacker_army.game.current_day,
            weeks_elapsed=0,
            current_threshold=initial_threshold,
            threshold_modifiers=threshold_modifiers,
            siege_engines_count=0,
            status="ongoing",
        )

        self.session.add(siege)
        self.session.commit()

        result["success"] = True
        result["siege_id"] = siege.id
        result["message"] = f"Siege of {stronghold.name} started by army {attacker_army.id}"

        return result

    def progress_siege_weekly(self, siege: Siege) -> dict:
        """Progress a siege by one week, applying weekly modifiers.

        Args:
            siege: The siege to progress

        Returns:
            Dictionary with weekly progression results
        """
        result = {
            "week_progressed": True,
            "threshold_change": 0,
            "gates_opened": False,
            "events": [],
        }

        # Apply default weekly modifier (-1 to threshold)
        weekly_modifiers = {"weekly": -1}
        siege.current_threshold += weekly_modifiers["weekly"]

        # Apply other possible modifiers
        modifiers_applied = []

        # Disease modifier
        # In a real implementation, this would be checked based on conditions
        if False:  # Placeholder for actual check
            weekly_modifiers["disease"] = -1
            siege.current_threshold += weekly_modifiers["disease"]
            modifiers_applied.append("disease")

        # Resupply modifier
        # In a real implementation, this would be checked based on defender supply status
        if False:  # Placeholder for actual check
            weekly_modifiers["resupply"] = 2
            siege.current_threshold += weekly_modifiers["resupply"]
            modifiers_applied.append("resupply")

        # Siege engines modifier
        # Each 10 siege engines reduces defensive bonus by 1
        if siege.siege_engines_count > 0:
            siege_engines_reduction = -(siege.siege_engines_count // 10)
            weekly_modifiers["siege_engines"] = siege_engines_reduction
            siege.current_threshold += siege_engines_reduction
            modifiers_applied.append(f"engines:{siege.siege_engines_count}")

        # Brutal trait: -1 additional threshold per week
        for army_id in siege.attacker_armies:
            army = self.session.get(Army, army_id)
            if army and army.commander:
                has_brutal = any(t.trait.name.lower() == "brutal" for t in army.commander.traits)
                if has_brutal:
                    weekly_modifiers["brutal"] = -1
                    siege.current_threshold += weekly_modifiers["brutal"]
                    modifiers_applied.append("brutal")
                    break

        # Update threshold modifiers list
        if not siege.threshold_modifiers:
            siege.threshold_modifiers = {}

        for key, value in weekly_modifiers.items():
            if key in siege.threshold_modifiers:
                siege.threshold_modifiers[key] += value
            else:
                siege.threshold_modifiers[key] = value

        # Roll 2d6 to check if gates open (traitor/negotiator)
        seed = generate_seed(
            siege.game_id,
            siege.started_on_day + siege.weeks_elapsed,
            "morning",
            f"siege_gates_{siege.stronghold_id}",
        )
        roll_result = roll_dice(seed, "2d6")
        dice_roll = roll_result["total"]
        if dice_roll > siege.current_threshold:
            siege.status = "gates_opened"
            result["gates_opened"] = True
            result["events"].append("Gates opened due to traitor or negotiation")

        # Increment weeks elapsed
        siege.weeks_elapsed += 1

        result["threshold_change"] = sum(weekly_modifiers.values())

        return result

    def launch_assault(
        self, attacker_armies: list[Army], stronghold: Stronghold, _battle_plan: str = ""
    ) -> dict:
        """Launch an assault on a stronghold.

        Args:
            attacker_armies: List of armies launching the assault
            stronghold: The stronghold being assaulted
            _battle_plan: Battle plan description (unused for now)

        Returns:
            Dictionary with assault results
        """
        result = {"success": False, "battle_result": None, "message": "", "events": []}

        # Get the defender army (garrison) if it exists
        defender_armies = []
        if hasattr(stronghold, "garrison") and stronghold.garrison:
            defender_armies = [stronghold.garrison]
        else:
            # If no garrison, stronghold is considered to have default garrison
            # In real implementation, this would create a default garrison army
            result["message"] = "No defending army found for assault"
            return result

        # Determine fortress defense bonus
        fortress_bonus = stronghold.defensive_bonus

        # Check for Defensive Engineer trait on defender (adds +2 to defense bonus)
        for defender_army in defender_armies:
            if defender_army.commander:  # type: ignore[truthy-bool]
                has_def_engineer = any(
                    t.trait.name.lower() == "defensive_engineer"
                    for t in defender_army.commander.traits  # type: ignore[union-attr]
                )
                if has_def_engineer:
                    fortress_bonus += 2
                    break

        # If gates are open, defense bonus is 0
        is_gates_open = stronghold.gates_open

        if is_gates_open:
            fortress_bonus = 0

        # Use battle service to resolve the assault
        try:
            battle_result = self.battle.resolve_battle(
                attacker_armies=attacker_armies,
                defender_armies=defender_armies,
                hex_id=stronghold.hex_id,  # Assuming stronghold has hex_id
                is_assault=True,
                fortress_defense_bonus=fortress_bonus,
            )

            result["success"] = True
            result["battle_result"] = battle_result
            result["message"] = "Assault completed"

        except Exception as e:
            result["message"] = f"Error resolving assault: {e!s}"
            return result

        return result

    def get_siege_engines_build_time(self, is_siege_engineer: bool) -> int:
        """Get time to build 10 siege engines based on traits.

        Args:
            is_siege_engineer: Whether a commander with Siege Engineer trait is present

        Returns:
            Time in days to build 10 siege engines
        """
        if is_siege_engineer:
            # Siege Engineer trait: Build 10 siege engines in 1 week (not 1 month)
            return 7  # 1 week in days
        # Default: 1 month to construct 10 engines
        return 30  # 1 month in days

    def build_siege_engines(self, _army: Army, count: int, is_siege_engineer: bool = False) -> dict:
        """Build siege engines for an army.

        Args:
            _army: Army building the engines (unused for now)
            count: Number of engines to build (must be multiple of 10)
            is_siege_engineer: Whether Siege Engineer trait is present (faster building)

        Returns:
            Dictionary with construction results
        """
        result = {"success": False, "engines_built": 0, "time_required_days": 0, "message": ""}

        # Validate count is multiple of 10
        if count % 10 != 0:
            result["message"] = "Siege engines must be built in groups of 10"
            return result

        # Calculate time required
        build_time_days = self.get_siege_engines_build_time(is_siege_engineer)
        total_time = (count // 10) * build_time_days

        result["time_required_days"] = total_time
        result["engines_built"] = count
        result["success"] = True
        result["message"] = f"Building {count} siege engines will take {total_time} days"

        # In real implementation, this would create an order to build siege engines
        # and return when they're completed

        return result

    def deconstruct_siege_engines(self, army: Army, count: int) -> dict:
        """Deconstruct siege engines and load onto wagons.

        Args:
            army: Army deconstructing the engines
            count: Number of engines to deconstruct (must be multiple of 10)

        Returns:
            Dictionary with deconstruction results
        """
        result = {
            "success": False,
            "engines_deconstructed": 0,
            "wagons_needed": 0,
            "time_required_days": 7,  # 1 week per detachment of 10
            "message": "",
        }

        # Validate count is multiple of 10
        if count % 10 != 0:
            result["message"] = "Siege engines must be deconstructed in groups of 10"
            return result

        # Calculate wagons needed (10 siege engines require 20 empty wagons)
        wagons_needed = count * 2  # According to RULES_IMPLEMENTATION_NOTES.md
        result["wagons_needed"] = wagons_needed

        # Check if army has enough empty wagons
        total_wagons = 0
        for detachment in army.detachments:
            total_wagons += detachment.wagon_count

        empty_wagons = (
            total_wagons  # This is a simplification; in reality, you'd need to check supply load
        )

        if empty_wagons < wagons_needed:
            result["message"] = (
                f"Not enough empty wagons: need {wagons_needed}, have {empty_wagons}"
            )
            return result

        result["engines_deconstructed"] = count
        result["success"] = True
        result["message"] = (
            f"Deconstructed {count} siege engines, requiring {wagons_needed} empty wagons"
        )

        # In real implementation, this would update the army's detachments
        # to remove siege engines and mark wagons as carrying engines

        return result

    def capture_stronghold(
        self, victor_army: Army, stronghold: Stronghold, allow_pillage: bool = False
    ) -> dict:
        """Process the capture of a stronghold.

        Args:
            victor_army: Army that captured the stronghold
            stronghold: The captured stronghold
            allow_pillage: Whether the army chooses to pillage

        Returns:
            Dictionary with capture results
        """
        result = {
            "success": False,
            "pillage_chosen": False,
            "loot_gained": 0,
            "supplies_gained": 0,
            "morale_change": 0,
            "new_noncombatants": 0,
            "message": "",
        }

        # Update stronghold ownership
        stronghold.controlling_faction_id = victor_army.commander.faction_id

        if allow_pillage:
            # Pillage option: -50% stronghold loot and supplies, +2 morale to army
            result["pillage_chosen"] = True
            result["loot_gained"] = stronghold.loot_held // 2
            result["supplies_gained"] = stronghold.supplies_held // 2
            result["morale_change"] = 2

            # Reduce stronghold resources by half
            stronghold.loot_held //= 2
            stronghold.supplies_held //= 2

            # Update army stats
            victor_army.loot_carried += result["loot_gained"]
            victor_army.supplies_current = min(
                victor_army.supplies_capacity,
                victor_army.supplies_current + result["supplies_gained"],
            )
            victor_army.morale_current = min(
                victor_army.morale_max, victor_army.morale_current + result["morale_change"]
            )

            result["message"] = (
                f"Stronghold pillaged, army gained {result['loot_gained']} loot, "
                f"{result['supplies_gained']} supplies, +{result['morale_change']} morale"
            )
        else:
            # No pillage: Check morale to maintain discipline
            success, consequence, roll = self.morale.check_morale(victor_army)

            if not success:
                result["message"] = (
                    f"No pillage but morale check failed (roll {roll}), "
                    f"army suffers '{consequence}' consequence"
                )
                # Apply the consequence in a real implementation
            else:
                result["message"] = (
                    "Stronghold captured without pillage, army discipline maintained"
                )

        # Add noncombatants based on stronghold type
        noncombatant_percentages = {"fortress": 0.05, "town": 0.10, "city": 0.15}
        stronghold_type = getattr(stronghold, "type", "town").lower()
        percentage = noncombatant_percentages.get(stronghold_type, 0.10)

        new_noncombatants = int(victor_army.noncombatant_count * percentage)
        result["new_noncombatants"] = new_noncombatants
        victor_army.noncombatant_count += new_noncombatants

        # Calculate supplies captured based on weeks under siege
        weeks_under_siege = getattr(stronghold, "weeks_siege", 0)  # Would come from siege record
        supply_multipliers = {"town": 10000, "fortress": 1000, "city": 100000}
        base_supply = supply_multipliers.get(stronghold_type, 10000)

        seed = generate_seed(
            victor_army.game_id,
            victor_army.game.current_day,
            victor_army.game.current_day_part,
            f"capture_supplies_{stronghold.id}",
        )
        roll_result = roll_dice(seed, "1d6")
        dice_roll = roll_result["total"]
        supplies_captured = max(0, (dice_roll - weeks_under_siege) * base_supply)
        result["supplies_gained"] += supplies_captured

        result["success"] = True

        return result
