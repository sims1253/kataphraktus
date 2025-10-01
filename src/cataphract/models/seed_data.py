"""Seed data initialization for catalog tables.

This module provides functions to initialize the catalog tables (traits and unit_types)
with the base game data from ruleset v1.1.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .army import UnitType
from .commander import Trait


def seed_traits(session: Session) -> None:
    """Seed the traits table with base 20 traits from ruleset v1.1.

    Args:
        session: SQLAlchemy session to use for database operations
    """
    # Check if traits already exist
    result = session.execute(select(Trait).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Traits already seeded

    traits = [
        Trait(
            name="beloved",
            description="+1 resting morale",
            scope_tags=["morale"],
            effect_data={"morale_resting_bonus": 1},
        ),
        Trait(
            name="brutal",
            description="Sieges -1 additional threshold/week",
            scope_tags=["siege"],
            effect_data={"siege_threshold_mod": -1},
        ),
        Trait(
            name="commando",
            description="Designate one detachment as skirmishers",
            scope_tags=["army_composition"],
            effect_data={"grant_skirmisher_slot": 1},
        ),
        Trait(
            name="crusader",
            description="+1 vs heretics/infidels in battle",
            scope_tags=["battle_mod"],
            effect_data={"battle_vs_infidel": 1},
        ),
        Trait(
            name="defensive_engineer",
            description="+2 defensive bonus when defending stronghold",
            scope_tags=["siege"],
            effect_data={"assault_defense_bonus": 2},
        ),
        Trait(
            name="duelist",
            description="-10 years for single combat, win ties",
            scope_tags=["single_combat"],
            effect_data={"age_modifier": -10, "win_ties": True},
        ),
        Trait(
            name="guardian",
            description="-5% casualties, -1/6 capture chance",
            scope_tags=["battle_mod"],
            effect_data={"casualty_reduction": 0.05, "capture_chance_mod": -1},
        ),
        Trait(
            name="honorable",
            description="No auto-pillage, -1/6 revolt chance",
            scope_tags=["operations"],
            effect_data={"no_auto_pillage": True, "revolt_chance_mod": -1},
        ),
        Trait(
            name="ironsides",
            description="+5 threshold when defending siege",
            scope_tags=["siege"],
            effect_data={"siege_defense_threshold": 5},
        ),
        Trait(
            name="logistician",
            description="+20% supply capacity, half column length",
            scope_tags=["logistics"],
            effect_data={"supply_capacity_mult": 1.2, "column_length_mult": 0.5},
        ),
        Trait(
            name="outrider",
            description="3-hex scouting/foraging with cavalry",
            scope_tags=["scouting", "logistics"],
            effect_data={"scouting_range_bonus": 1, "foraging_range_bonus": 1},
        ),
        Trait(
            name="poet",
            description="Morale rolls +2 for consequence determination",
            scope_tags=["morale"],
            effect_data={"morale_roll_bonus": 2},
        ),
        Trait(
            name="raider",
            description="+20% loot captured, +10% supplies foraged",
            scope_tags=["logistics"],
            effect_data={"loot_mult": 1.2, "foraging_mult": 1.1},
        ),
        Trait(
            name="ranger",
            description="Bad weather doesn't reduce scouting",
            scope_tags=["scouting"],
            effect_data={"ignore_weather_penalty": True},
        ),
        Trait(
            name="scholar",
            description="Can memorize wizard spells",
            scope_tags=["magic"],
            effect_data={"can_cast_spells": True},
        ),
        Trait(
            name="siege_engineer",
            description="Build 10 siege engines in 1 week",
            scope_tags=["siege"],
            effect_data={"siege_engine_build_weeks": 1},
        ),
        Trait(
            name="spartan",
            description="Half noncombatants, half noncombatant gain",
            scope_tags=["logistics"],
            effect_data={"noncombatant_mult": 0.5},
        ),
        Trait(
            name="stubborn",
            description="No morale loss on defeat",
            scope_tags=["morale"],
            effect_data={"no_defeat_morale_loss": True},
        ),
        Trait(
            name="vanquisher",
            description="+5% enemy casualties, +1/6 capture chance",
            scope_tags=["battle_mod"],
            effect_data={"enemy_casualty_bonus": 0.05, "capture_chance_mod": 1},
        ),
        Trait(
            name="veteran",
            description="Never routs on defeat",
            scope_tags=["morale"],
            effect_data={"no_rout": True},
        ),
    ]

    session.add_all(traits)
    session.commit()


def seed_unit_types(session: Session) -> None:
    """Seed the unit_types table with base 7 unit types from ruleset v1.1.

    Args:
        session: SQLAlchemy session to use for database operations
    """
    # Check if unit types already exist
    result = session.execute(select(UnitType).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Unit types already seeded

    unit_types = [
        UnitType(
            name="infantry",
            category="infantry",
            battle_multiplier=1.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
            special_abilities={},
        ),
        UnitType(
            name="heavy_infantry",
            category="infantry",
            battle_multiplier=2.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
            special_abilities={},
        ),
        UnitType(
            name="cavalry",
            category="cavalry",
            battle_multiplier=2.0,
            supply_cost_per_day=10,
            can_travel_offroad=True,
            special_abilities={"scouting_bonus": 1, "foraging_bonus": 1},
        ),
        UnitType(
            name="heavy_cavalry",
            category="cavalry",
            battle_multiplier=4.0,
            supply_cost_per_day=10,
            can_travel_offroad=True,
            special_abilities={"scouting_bonus": 1, "foraging_bonus": 1},
        ),
        UnitType(
            name="skirmisher",
            category="infantry",
            battle_multiplier=1.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
            special_abilities={
                "acts_as_cavalry_for_scouting": True,
                "acts_as_cavalry_for_foraging": True,
                "acts_as_cavalry_for_fording": True,
                "harrying_bonus": 1,
                "offroad_full_speed": True,
            },
        ),
        UnitType(
            name="siege_engines",
            category="siege",
            battle_multiplier=0.0,
            supply_cost_per_day=0,
            can_travel_offroad=False,
            special_abilities={"reduces_fortress_bonus": True},
        ),
        UnitType(
            name="wizard",
            category="special",
            battle_multiplier=0.0,
            supply_cost_per_day=0,
            can_travel_offroad=True,
            special_abilities={"counts_as_infantry": True, "independence_risk": 1},
        ),
    ]

    session.add_all(unit_types)
    session.commit()


def seed_all_catalog_data(session: Session) -> None:
    """Seed all catalog tables with base game data.

    Args:
        session: SQLAlchemy session to use for database operations
    """
    seed_traits(session)
    seed_unit_types(session)
