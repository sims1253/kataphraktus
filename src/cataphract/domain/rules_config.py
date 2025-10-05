"""Declarative rule configuration for the new domain layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SupplyRules:
    """Supply, foraging, and torching constants."""

    infantry_capacity: int = 15
    noncombatant_capacity: int = 15
    cavalry_capacity: int = 75
    wagon_capacity: int = 1000
    infantry_consumption: int = 1
    noncombatant_consumption: int = 1
    cavalry_consumption: int = 10
    wagon_consumption: int = 10
    base_noncombatant_ratio: float = 0.25
    spartan_ratio: float = 0.125
    exclusive_skirmisher_ratio: float = 0.10
    wizard_supply_encumbrance: int = 1000
    foraging_multiplier: int = 500
    foraging_limit_per_season: int = 5
    torch_revolt_chance: int = 1  # out of 6
    forage_revolt_chance_repeat: int = 2  # out of 6
    torch_revolt_hostile_modifier: int = 1  # +1 hostile, i.e. 2-in-6
    forage_revolt_hostile_modifier: int = 1
    revolt_cooldown_days: int = 365
    torched_foraging_reset_day: int = 0  # resets next spring via seasonal tick


@dataclass(frozen=True, slots=True)
class MoraleRules:
    """Selected morale-related constants."""

    default_resting: int = 9
    default_max: int = 12
    forced_march_morale_loss_per_week: int = 1
    starvation_morale_loss_per_day: int = 1
    starvation_dissolution_days: int = 14


@dataclass(frozen=True, slots=True)
class MovementRules:
    """Movement rates and penalties."""

    road_standard_miles_per_day: int = 12
    road_forced_miles_per_day: int = 18
    offroad_standard_miles_per_day: int = 6
    offroad_forced_miles_per_day: int = 9
    night_miles_per_day: int = 6
    night_forced_miles_per_day: int = 12
    cavalry_forced_multiplier: int = 2
    column_length_threshold: float = 6.0
    column_capped_standard_speed: int = 6
    column_capped_forced_speed: int = 12
    night_wrong_path_chance: int = 2  # out of 6


@dataclass(frozen=True, slots=True)
class VisibilityRules:
    """Scouting/visibility radii."""

    base_radius: int = 1
    cavalry_bonus: int = 1
    outrider_bonus: int = 1
    bad_weather_penalty: int = 1
    very_bad_weather_penalty: int = 2


@dataclass(frozen=True, slots=True)
class RevoltOutcomeRules:
    """Parameters for revolt armies."""

    infantry_die_size: int = 20
    infantry_multiplier: int = 500


@dataclass(frozen=True, slots=True)
class BattleRules:
    """Parameters for field and assault battles."""

    rout_threshold: int = 2
    retreat_hexes_min: int = 1
    retreat_hexes_max: int = 6
    retreat_supply_loss_die: int = 6
    retreat_supply_loss_multiplier: int = 10
    capture_chance_minor: int = 1  # out of 6 when roll diff 4-5
    capture_chance_major: int = 2  # out of 6 when roll diff 6+
    morale_penalty_on_rout: int = 2
    loot_capture_fraction: float = 0.5
    multi_side_numeric_bonus_ratio: float = 0.1


@dataclass(frozen=True, slots=True)
class SiegeRules:
    """Parameters for siege progression and assaults."""

    town_threshold: int = 10
    city_threshold: int = 15
    fortress_threshold: int = 20
    default_modifier: int = -1  # per week
    disease_modifier: int = -1
    resupply_modifier: int = 2
    attacked_modifier: int = 1
    siege_engine_reduction_per_detachment: int = 1
    starvation_threshold: int = 0
    surrender_check_target: int = 12


@dataclass(frozen=True, slots=True)
class NavalRules:
    """Movement and embarkation figures for naval actions."""

    friendly_miles_per_day: int = 48
    hostile_miles_per_day: int = 36
    embark_days: int = 1
    disembark_days: int = 1
    riverine_miles_per_day: int = 36
    blockade_supply_modifier: float = 0.5


@dataclass(frozen=True, slots=True)
class MessagingRules:
    """Messenger travel and success chances."""

    friendly_success_numerator: int = 19
    friendly_success_denominator: int = 20
    hostile_success_numerator: int = 5
    hostile_success_denominator: int = 6
    friendly_miles_per_day: int = 48
    hostile_miles_per_day: int = 36
    neutral_miles_per_day: int = 42


@dataclass(frozen=True, slots=True)
class MercenaryRules:
    """Mercenary contract upkeep constants."""

    infantry_upkeep_per_day: int = 1
    cavalry_upkeep_per_day: int = 3
    grace_days_without_pay: int = 3
    morale_penalty_unpaid: int = 1
    desertion_chance_numerator: int = 1
    desertion_chance_denominator: int = 6


@dataclass(frozen=True, slots=True)
class RecruitmentRules:
    """Recruitment timing and revolt parameters."""

    muster_duration_days: int = 30
    recruitment_cooldown_days: int = 365
    revolt_chance: int = 1  # out of 6
    recently_conquered_days: int = 90


@dataclass(frozen=True, slots=True)
class OperationsRules:
    """Espionage/special operation tuning."""

    base_success_target: int = 7
    simple_modifier: int = 2
    complex_modifier: int = -2
    hostile_territory_modifier: int = -1
    loot_cost_default: int = 100


@dataclass(frozen=True, slots=True)
class RulesConfig:
    """Top-level configuration container for all subsystems."""

    supply: SupplyRules = SupplyRules()
    morale: MoraleRules = MoraleRules()
    movement: MovementRules = MovementRules()
    visibility: VisibilityRules = VisibilityRules()
    revolt_outcome: RevoltOutcomeRules = RevoltOutcomeRules()
    battle: BattleRules = BattleRules()
    siege: SiegeRules = SiegeRules()
    naval: NavalRules = NavalRules()
    messaging: MessagingRules = MessagingRules()
    mercenaries: MercenaryRules = MercenaryRules()
    operations: OperationsRules = OperationsRules()
    recruitment: RecruitmentRules = RecruitmentRules()


DEFAULT_RULES = RulesConfig()
