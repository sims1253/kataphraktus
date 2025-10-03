"""Battle Resolution Service for Cataphract.

This module provides functions for resolving battles according to the Cataphract rules
with 2d6 mechanics and various modifiers.
"""

from sqlalchemy.orm import Session

from cataphract.domain.battle_data import (
    BattleContext,
    BattleModifierParameters,
    BattleOutcome,
    BattleParameters,
    BattleRollResults,
)
from cataphract.models import Army
from cataphract.models.battle import Battle as BattleModel
from cataphract.utils.rng import generate_seed, random_int, roll_dice

# Battle outcome thresholds
ROLL_DIFF_MINOR_VICTORY = 2  # 2-3 difference
ROLL_DIFF_MINOR_VICTORY_MAX = 3  # Upper bound for minor victory
ROLL_DIFF_MAJOR_VICTORY = 4  # 4-5 difference
ROLL_DIFF_MAJOR_VICTORY_MAX = 5  # Upper bound for major victory
ROLL_DIFF_DECISIVE_VICTORY = 6  # 6+ difference
CAPTURE_CHANCE_MINOR = 1  # 1/6 for 4-5 difference
CAPTURE_CHANCE_MAJOR = 2  # 2/6 for 6+ difference
ROUT_CHANCE = 3  # 3/6 chance to rout


class BattleService:
    """Service for handling battle resolution in Cataphract."""

    def __init__(self, session: Session):
        self.session = session

    def calculate_battle_modifier(
        self,
        params: BattleModifierParameters,
    ) -> int:
        """Calculate battle modifiers for an army based on various factors.

        Args:
            params: BattleModifierParameters containing all necessary information

        Returns:
            Total battle modifier
        """
        modifiers = 0

        # Terrain modifiers
        modifiers += self._calculate_terrain_modifiers(params)

        # Army status modifiers
        modifiers += self._calculate_army_status_modifiers(params)

        # Assault modifiers
        modifiers += self._calculate_assault_modifiers(params)

        # Commander trait modifiers
        modifiers += self._calculate_commander_trait_modifiers(params)

        return modifiers

    def _calculate_terrain_modifiers(self, params: BattleModifierParameters) -> int:
        """Calculate terrain-based modifiers."""
        modifiers = 0

        # Advantageous terrain for defenders
        if params.hex_terrain in ["hills", "forest", "mountain"] and params.is_defender:
            modifiers += 1

        # Rough terrain for attackers
        if params.hex_terrain in ["hills", "forest", "mountain"] and not params.is_defender:
            modifiers -= 1

        return modifiers

    def _calculate_army_status_modifiers(self, params: BattleModifierParameters) -> int:
        """Calculate modifiers based on army status."""
        modifiers = 0

        # Undersupplied
        if params.army.is_undersupplied:
            modifiers -= 1

        # Sick or exhausted
        if params.army.status_effects and params.army.status_effects.get(
            "sick_or_exhausted", {}
        ).get("active"):
            modifiers -= 1

        # Bad weather
        if params.weather in ["bad", "storm", "very_bad"]:
            modifiers -= 1

        # Out of formation
        if params.army.status in ["foraging", "resting"]:
            modifiers -= 2

        return modifiers

    def _calculate_assault_modifiers(self, params: BattleModifierParameters) -> int:
        """Calculate assault-specific modifiers."""
        modifiers = 0

        if params.is_assault and params.is_attacker:
            # In assaults, attackers suffer -1 to their roll
            modifiers -= 1

        return modifiers

    def _calculate_commander_trait_modifiers(self, params: BattleModifierParameters) -> int:
        """Calculate modifiers from commander traits."""
        modifiers = 0

        if not params.army.commander:
            return modifiers

        for trait in params.army.commander.traits:
            trait_name = trait.trait.name.lower()
            if trait_name == "crusader" and params.is_attacker:
                # Assuming there's a way to check if fighting heretics/infidels
                modifiers += 1
            # Other traits (guardian, vanquisher, veteran, stubborn) affect other aspects
            # not battle roll, so they're documented but don't add modifiers here

        return modifiers

    def calculate_army_composition_for_battle(self, army: Army, is_assault: bool = False) -> int:
        """Calculate effective army size for battle composition calculations.

        Args:
            army: The army to calculate for
            is_assault: Whether this is an assault (cavalry don't count double)

        Returns:
            Effective army size for composition calculations
        """
        total_size = 0

        for detachment in army.detachments:
            base_size = detachment.soldier_count
            multiplier = detachment.unit_type.battle_multiplier

            # In assaults, cavalry don't count as double for determining troop totals
            if is_assault and detachment.unit_type.category == "cavalry":
                multiplier = 1.0

            total_size += int(base_size * multiplier)

        return total_size

    def calculate_numerical_advantage_modifier(
        self, army: Army, opposing_army: Army, is_assault: bool = False
    ) -> int:
        """Calculate numerical advantage modifier based on army compositions.

        Args:
            army: The army to calculate modifier for
            opposing_army: The opposing army
            is_assault: Whether this is an assault (cavalry don't count double)

        Returns:
            Numerical advantage modifier
        """
        army_size = self.calculate_army_composition_for_battle(army, is_assault)
        opposing_size = self.calculate_army_composition_for_battle(opposing_army, is_assault)

        if opposing_size == 0:
            return 0  # Prevent division by zero

        # Calculate percentage advantage: (army_size - opposing_size) / opposing_size
        advantage_ratio = (army_size - opposing_size) / opposing_size
        # Each 100% advantage = +1 modifier
        modifier = int(advantage_ratio)

        # Cap at reasonable values to prevent extreme modifiers
        return max(-3, min(3, modifier))

    def calculate_morale_advantage_modifier(self, army: Army, opposing_army: Army) -> int:
        """Calculate morale advantage modifier.

        Args:
            army: The army to calculate modifier for
            opposing_army: The opposing army

        Returns:
            Morale advantage modifier
        """
        # Calculate difference in current morale
        return army.morale_current - opposing_army.morale_current
        # Each point of morale advantage = +1 modifier

    def resolve_battle(self, parameters: BattleParameters) -> BattleModel:
        """Resolve a battle between two or more armies following Cataphract rules.

        Args:
            parameters: BattleParameters containing all battle information

        Returns:
            Battle model with resolution results
        """

        # Calculate total composition for each side (for numerical advantage)
        for army in parameters.attacker_armies:
            self.calculate_army_composition_for_battle(army, parameters.is_assault)
        for army in parameters.defender_armies:
            self.calculate_army_composition_for_battle(army, parameters.is_assault)

        # Calculate rolls for all armies
        attacker_rolls, defender_rolls = self._calculate_army_rolls(parameters)

        # Create battle context
        context = self._create_battle_context(parameters, attacker_rolls, defender_rolls)

        # Calculate battle outcomes
        casualties, morale_changes, routed_armies, commanders_captured = (
            self._calculate_battle_outcomes(context)
        )

        # Create battle model
        roll_results = BattleRollResults(
            attacker_rolls=attacker_rolls,
            defender_rolls=defender_rolls,
        )
        outcome = BattleOutcome(
            casualties=casualties,
            morale_changes=morale_changes,
            routed_armies=routed_armies,
            commanders_captured=commanders_captured,
        )
        battle = self._create_battle_model(
            context,
            roll_results,
            outcome,
        )

        # Apply results to armies
        self._apply_battle_results_to_armies(context, casualties, morale_changes)

        return battle

    # Helper methods for battle resolution
    def _calculate_army_rolls(
        self, parameters: BattleParameters
    ) -> tuple[dict[int, dict], dict[int, dict]]:
        """Calculate battle rolls for all armies in the battle.

        Args:
            parameters: Battle parameters containing all necessary information

        Returns:
            Tuple of (attacker_rolls, defender_rolls) dictionaries
        """
        attacker_rolls = {}
        defender_rolls = {}

        # Calculate rolls for attacking armies
        for army in parameters.attacker_armies:
            modifier_params = BattleModifierParameters(
                army=army,
                is_attacker=True,
                is_defender=False,
                hex_terrain=parameters.hex_terrain,
                weather=parameters.weather,
                is_assault=parameters.is_assault,
            )
            modifiers = self.calculate_battle_modifier(modifier_params)

            # Calculate numerical and morale advantage modifiers against ALL defenders combined
            if parameters.defender_armies:
                # Calculate total defender size for numerical advantage
                total_defender_size = sum(
                    self.calculate_army_composition_for_battle(defender_army, parameters.is_assault)
                    for defender_army in parameters.defender_armies
                )
                army_size = self.calculate_army_composition_for_battle(army, parameters.is_assault)

                if total_defender_size > 0:
                    # Calculate numerical advantage against total defender force
                    advantage_ratio = (army_size - total_defender_size) / total_defender_size
                    numerical_modifier = int(advantage_ratio)
                    numerical_modifier = max(-3, min(3, numerical_modifier))
                    modifiers += numerical_modifier

                # Calculate average morale advantage
                avg_defender_morale = sum(
                    defender.morale_current for defender in parameters.defender_armies
                ) / len(parameters.defender_armies)
                morale_modifier = army.morale_current - int(avg_defender_morale)
                modifiers += morale_modifier

            # Roll 2d6
            seed = generate_seed(
                army.id, army.game.current_day, army.game.current_day_part, "battle_roll"
            )
            roll_result = roll_dice(seed, "2d6")
            dice_roll = roll_result["total"]
            total_roll = dice_roll + modifiers

            attacker_rolls[army.id] = {
                "roll": dice_roll,
                "modifiers": modifiers,
                "total": total_roll,
            }

        # Calculate rolls for defending armies
        for army in parameters.defender_armies:
            modifier_params = BattleModifierParameters(
                army=army,
                is_attacker=False,
                is_defender=True,
                hex_terrain=parameters.hex_terrain,
                weather=parameters.weather,
                is_assault=parameters.is_assault,
            )
            modifiers = self.calculate_battle_modifier(modifier_params)

            # Add fortress defense bonus if assault
            if parameters.is_assault:
                modifiers += parameters.fortress_defense_bonus

            # Calculate numerical and morale advantage modifiers against ALL attackers combined
            if parameters.attacker_armies:
                # Calculate total attacker size for numerical advantage
                total_attacker_size = sum(
                    self.calculate_army_composition_for_battle(attacker_army, parameters.is_assault)
                    for attacker_army in parameters.attacker_armies
                )
                army_size = self.calculate_army_composition_for_battle(army, parameters.is_assault)

                if total_attacker_size > 0:
                    # Calculate numerical advantage against total attacker force
                    advantage_ratio = (army_size - total_attacker_size) / total_attacker_size
                    numerical_modifier = int(advantage_ratio)
                    numerical_modifier = max(-3, min(3, numerical_modifier))
                    modifiers += numerical_modifier

                # Calculate average morale advantage
                avg_attacker_morale = sum(
                    attacker.morale_current for attacker in parameters.attacker_armies
                ) / len(parameters.attacker_armies)
                morale_modifier = army.morale_current - int(avg_attacker_morale)
                modifiers += morale_modifier

            # Roll 2d6
            seed = generate_seed(
                army.id, army.game.current_day, army.game.current_day_part, "battle_defender_roll"
            )
            roll_result = roll_dice(seed, "2d6")
            dice_roll = roll_result["total"]
            total_roll = dice_roll + modifiers

            defender_rolls[army.id] = {
                "roll": dice_roll,
                "modifiers": modifiers,
                "total": total_roll,
            }

        return attacker_rolls, defender_rolls

    def _create_battle_context(
        self, parameters: BattleParameters, attacker_rolls: dict, defender_rolls: dict
    ) -> BattleContext:
        """Create a battle context with calculated rolls and outcomes.

        Args:
            parameters: Battle parameters
            attacker_rolls: Dictionary of attacker roll results
            defender_rolls: Dictionary of defender roll results

        Returns:
            BattleContext with calculated outcomes
        """
        attacker_highest = max([result["total"] for result in attacker_rolls.values()], default=0)
        defender_highest = max([result["total"] for result in defender_rolls.values()], default=0)

        # Determine victor
        winning_side = "attacker" if attacker_highest > defender_highest else "defender"

        return BattleContext(
            parameters=parameters,
            attacker_rolls={army_id: result["total"] for army_id, result in attacker_rolls.items()},
            defender_rolls={army_id: result["total"] for army_id, result in defender_rolls.items()},
            highest_attacker_roll=attacker_highest,
            highest_defender_roll=defender_highest,
            winning_side=winning_side,
        )

    def _calculate_battle_outcomes(self, context: BattleContext) -> tuple[dict, dict, list, list]:
        """Calculate casualties, morale changes, routing, and captures for all armies.

        Args:
            context: Battle context with roll results and parameters

        Returns:
            Tuple of (casualties, morale_changes, routed_armies, commanders_captured)
        """
        # Get the winning and losing sides
        if context.winning_side == "attacker":
            victor_armies = context.attacker_armies
            loser_armies = context.defender_armies
            roll_difference = context.highest_attacker_roll - context.highest_defender_roll
        else:
            victor_armies = context.defender_armies
            loser_armies = context.attacker_armies
            roll_difference = context.highest_defender_roll - context.highest_attacker_roll

        # Initialize result dictionaries
        casualties = {}
        morale_changes = {}
        routed_armies = []
        commanders_captured = []

        # Create outcome object for modifications
        outcome = BattleOutcome(
            casualties=casualties,
            morale_changes=morale_changes,
            routed_armies=routed_armies,
            commanders_captured=commanders_captured,
        )

        # Set base casualties and morale for all armies
        for army in context.all_armies:
            casualties[army.id] = {
                "percentage": 5,
                "count": int(army.daily_supply_consumption * 0.05),
            }
            morale_changes[army.id] = 0

        # Handle tie case
        if roll_difference == 0:
            if context.winning_side == "defender":
                for army in context.attacker_armies:
                    outcome.morale_changes[army.id] -= 1
            else:
                for army in context.defender_armies:
                    outcome.morale_changes[army.id] -= 1

        # Apply outcomes based on roll difference
        self._apply_outcome_by_roll_difference(
            context,
            roll_difference,
            victor_armies,
            loser_armies,
            outcome,
        )

        # Apply assault-specific consequences
        if context.parameters.is_assault:
            self._apply_assault_consequences(context, casualties)

        # Apply trait-based modifications
        self._apply_trait_modifications(context, casualties)

        return casualties, morale_changes, routed_armies, commanders_captured

    def _apply_outcome_by_roll_difference(
        self,
        context: BattleContext,
        roll_difference: int,
        victor_armies: list,
        loser_armies: list,
        outcome: BattleOutcome,
    ):
        """Apply battle outcomes based on the roll difference.

        Args:
            context: Battle context
            roll_difference: Difference between winning and losing rolls
            victor_armies: List of winning armies
            loser_armies: List of losing armies
            outcome: BattleOutcome container to modify
        """
        if roll_difference == 0:
            self._apply_defender_holds_outcome(loser_armies, outcome)
        elif roll_difference == 1:
            self._apply_minor_difference_outcome(loser_armies, outcome)
        elif ROLL_DIFF_MINOR_VICTORY <= roll_difference <= ROLL_DIFF_MINOR_VICTORY_MAX:
            self._apply_minor_victory_outcome(victor_armies, loser_armies, outcome)
        elif ROLL_DIFF_MAJOR_VICTORY <= roll_difference <= ROLL_DIFF_MAJOR_VICTORY_MAX:
            self._apply_major_victory_outcome(context, victor_armies, loser_armies, outcome)
        elif roll_difference >= ROLL_DIFF_DECISIVE_VICTORY:
            self._apply_decisive_victory_outcome(context, victor_armies, loser_armies, outcome)

    def _apply_defender_holds_outcome(self, loser_armies: list, outcome: BattleOutcome) -> None:
        """Apply outcome when defender holds (roll difference = 0)."""
        for army in loser_armies:
            outcome.morale_changes[army.id] -= 1

    def _apply_minor_difference_outcome(self, loser_armies: list, outcome: BattleOutcome) -> None:
        """Apply outcome for minor roll difference (1)."""
        for army in loser_armies:
            outcome.casualties[army.id]["percentage"] = 10
            outcome.casualties[army.id]["count"] = int(army.daily_supply_consumption * 0.10)
            outcome.morale_changes[army.id] -= 1

    def _apply_minor_victory_outcome(
        self, victor_armies: list, loser_armies: list, outcome: BattleOutcome
    ) -> None:
        """Apply outcome for minor victory."""
        for army in victor_armies:
            outcome.morale_changes[army.id] += 1
        for army in loser_armies:
            outcome.casualties[army.id]["percentage"] = 10
            outcome.casualties[army.id]["count"] = int(army.daily_supply_consumption * 0.10)
            outcome.morale_changes[army.id] -= 2

    def _apply_major_victory_outcome(
        self,
        context: BattleContext,
        victor_armies: list,
        loser_armies: list,
        outcome: BattleOutcome,
    ) -> None:
        """Apply outcome for major victory."""
        for army in victor_armies:
            outcome.morale_changes[army.id] += 2
        for army in loser_armies:
            outcome.casualties[army.id]["percentage"] = 15
            outcome.casualties[army.id]["count"] = int(army.daily_supply_consumption * 0.15)
            outcome.morale_changes[army.id] -= 2

        # Calculate captures
        self._calculate_commander_captures(
            context, loser_armies, outcome.commanders_captured, CAPTURE_CHANCE_MINOR
        )

    def _apply_decisive_victory_outcome(
        self,
        context: BattleContext,
        victor_armies: list,
        loser_armies: list,
        outcome: BattleOutcome,
    ) -> None:
        """Apply outcome for decisive victory."""
        for army in victor_armies:
            outcome.morale_changes[army.id] += 2
        for army in loser_armies:
            outcome.casualties[army.id]["percentage"] = 20
            outcome.casualties[army.id]["count"] = int(army.daily_supply_consumption * 0.20)
            outcome.morale_changes[army.id] -= 2

        # Calculate captures with higher chance
        self._calculate_commander_captures(
            context, loser_armies, outcome.commanders_captured, CAPTURE_CHANCE_MAJOR
        )

        # Check for routing
        self._check_for_routing(context, loser_armies, outcome.routed_armies)

    def _calculate_commander_captures(
        self,
        context: BattleContext,
        loser_armies: list,
        commanders_captured: list,
        base_capture_chance: int,
    ):
        """Calculate commander captures for losing armies.

        Args:
            context: Battle context
            loser_armies: List of losing armies
            commanders_captured: List to add captured commanders to
            base_capture_chance: Base capture chance (1-6 on d6)
        """
        for army in loser_armies:
            capture_chance = base_capture_chance

            # Check for Vanquisher on victor side
            for victor_army in context.all_armies:
                if victor_army.commander and (
                    (victor_army in context.attacker_armies and context.winning_side == "attacker")
                    or (
                        victor_army in context.defender_armies
                        and context.winning_side == "defender"
                    )
                ):
                    has_vanquisher = any(
                        t.trait.name.lower() == "vanquisher" for t in victor_army.commander.traits
                    )
                    if has_vanquisher:
                        capture_chance += 1
                        break

            # Check for Guardian on losing army
            if army.commander:
                has_guardian = any(
                    t.trait.name.lower() == "guardian" for t in army.commander.traits
                )
                if has_guardian:
                    capture_chance = max(0, capture_chance - 1)

            # Apply capture roll
            if capture_chance > 0 and army.commander_id:
                capture_seed = generate_seed(
                    army.id,
                    army.game.current_day,
                    army.game.current_day_part,
                    f"capture_commander_{army.id}",
                )
                result = random_int(capture_seed, 1, 6)
                if result["value"] <= capture_chance:
                    commanders_captured.append(army.commander_id)

    def _check_for_routing(self, _context: BattleContext, loser_armies: list, routed_armies: list):
        """Check for routing in losing armies.

        Args:
            context: Battle context
            loser_armies: List of losing armies
            routed_armies: List to add routed armies to
        """
        for army in loser_armies:
            route_seed = generate_seed(
                army.id, army.game.current_day, army.game.current_day_part, f"route_check_{army.id}"
            )
            result = random_int(route_seed, 1, 6)
            if result["value"] <= ROUT_CHANCE:  # 3/6 chance from rules
                routed_armies.append(army.id)

    def _apply_assault_consequences(self, context: BattleContext, casualties: dict):
        """Apply assault-specific additional casualties.

        Args:
            context: Battle context
            casualties: Casualties dictionary to modify
        """
        # The losing side takes an additional 10% casualties in assaults
        loser_side = (
            context.defender_armies
            if context.winning_side == "attacker"
            else context.attacker_armies
        )

        for army in loser_side:
            if army.id in casualties:
                casualties[army.id]["percentage"] += 10
                casualties[army.id]["count"] = int(
                    army.daily_supply_consumption * casualties[army.id]["percentage"] / 100
                )

    def _apply_trait_modifications(self, context: BattleContext, casualties: dict):
        """Apply trait-based casualty modifications.

        Args:
            context: Battle context
            casualties: Casualties dictionary to modify
        """
        # Apply Vanquisher trait to increase enemy casualties by 5%
        for army in context.all_armies:
            if army.commander:
                has_vanquisher = any(
                    t.trait.name.lower() == "vanquisher" for t in army.commander.traits
                )
                if has_vanquisher:
                    # Increase casualties for opposing side armies by 5%
                    opposing_armies = (
                        context.defender_armies
                        if army in context.attacker_armies
                        else context.attacker_armies
                    )
                    for opposing_army in opposing_armies:
                        if opposing_army.id in casualties:
                            casualties[opposing_army.id]["percentage"] += 5
                            casualties[opposing_army.id]["count"] = int(
                                opposing_army.daily_supply_consumption
                                * casualties[opposing_army.id]["percentage"]
                                / 100
                            )

        # Apply Guardian trait casualty reduction (5% fewer casualties)
        for army in context.all_armies:
            if army.commander and army.id in casualties:
                has_guardian = any(
                    t.trait.name.lower() == "guardian" for t in army.commander.traits
                )
                if has_guardian:
                    # Reduce casualties by 5%
                    casualties[army.id]["percentage"] = max(
                        0, casualties[army.id]["percentage"] - 5
                    )
                    casualties[army.id]["count"] = int(
                        army.daily_supply_consumption * casualties[army.id]["percentage"] / 100
                    )

    def _create_battle_model(
        self,
        context: BattleContext,
        roll_results: BattleRollResults,
        outcome: BattleOutcome,
    ) -> BattleModel:
        """Create the final battle model.

        Args:
            context: Battle context with all parameters
            roll_results: Battle roll results
            outcome: Battle outcome results

        Returns:
            BattleModel with all battle results
        """
        # Get roll difference
        if context.winning_side == "attacker":
            roll_difference = context.highest_attacker_roll - context.highest_defender_roll
        else:
            roll_difference = context.highest_defender_roll - context.highest_attacker_roll

        return BattleModel(
            game_id=context.attacker_armies[0].game_id
            if context.attacker_armies
            else context.defender_armies[0].game_id,
            game_day=0,  # This would be set by caller
            hex_id=context.parameters.hex_id,
            battle_type="assault" if context.parameters.is_assault else "field",
            attacker_side=[army.id for army in context.attacker_armies],
            defender_side=[army.id for army in context.defender_armies],
            attacker_rolls=roll_results.attacker_rolls,
            defender_rolls=roll_results.defender_rolls,
            victor_side=context.winning_side,
            roll_difference=roll_difference,
            casualties=outcome.casualties,
            morale_changes=outcome.morale_changes,
            commanders_captured=outcome.commanders_captured,
            loot_captured=0,  # Would be calculated based on victory
            routed_armies=outcome.routed_armies,
        )

    def _apply_battle_results_to_armies(
        self, context: BattleContext, casualties: dict, morale_changes: dict
    ):
        """Apply battle results to army objects.

        Args:
            context: Battle context
            casualties: Casualties dictionary
            morale_changes: Morale changes dictionary
        """
        for army_id, stats in casualties.items():
            # Find the army by ID
            army = next((a for a in context.all_armies if a.id == army_id), None)
            if army:
                # Apply casualties
                army.supplies_current = max(0, army.supplies_current - stats["count"])
                # Apply morale changes
                army.morale_current = max(
                    0, min(army.morale_max, army.morale_current + morale_changes[army_id])
                )


def calculate_morale_check_result(morale: int) -> tuple[bool, str, int]:
    """Calculate result of a morale check using 2d6.

    Args:
        morale: Army's current morale

    Returns:
        Tuple of (success, consequence_type, consequence_roll)
    """
    # Use fixed seed for testing - in production this should be deterministic
    seed = generate_seed(1, 1, "morning", "morale_check")
    roll_result = roll_dice(seed, "2d6")
    roll = roll_result["total"]

    if roll <= morale:
        return True, "army_holds", roll
    # Failure case - use roll to determine consequence
    consequence_map = {
        2: "mutiny",
        3: "mass_desertion",
        4: "detachments_defect",
        5: "major_desertion",
        6: "army_splits",
        7: "random_detachment_defects",
        8: "desertion",
        9: "detachments_depart_2d6_days",
        10: "camp_followers",
        11: "random_detachment_depart_2d6_days",
        12: "no_consequences",
    }
    consequence = consequence_map.get(roll, "no_consequences")
    return False, consequence, roll
