"""Integration tests for Army Management Service.

Tests complete workflows involving multiple army service operations
and interactions with the database.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.cataphract.models import (
    Army,
    Base,
    Commander,
    CommanderTrait,
    Detachment,
    Faction,
    Game,
    Hex,
    Trait,
    UnitType,
)
from src.cataphract.services.army_service import (
    merge_armies,
    split_army,
    transfer_supplies,
    update_army_composition,
    validate_army_composition,
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create a new database session for testing."""
    sessionmaker_class = sessionmaker(bind=engine)
    session = sessionmaker_class()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def game(session):
    """Create a test game."""
    game = Game(
        name="Integration Test Game",
        start_date=date(2025, 1, 1),
        current_day=0,
        current_day_part="morning",
        tick_schedule="daily",
        map_width=20,
        map_height=20,
        season="spring",
        status="active",
    )
    session.add(game)
    session.commit()
    return game


@pytest.fixture
def faction(session, game):
    """Create a test faction."""
    faction = Faction(
        game_id=game.id,
        name="Empire",
        description="The mighty empire",
        color="#0000FF",
        special_rules={},
        unique_units=[],
    )
    session.add(faction)
    session.commit()
    return faction


@pytest.fixture
def hex_map(session, game):
    """Create a small hex map for testing."""
    hexes = []
    for q in range(5):
        for r in range(5):
            hex_tile = Hex(
                game_id=game.id,
                q=q,
                r=r,
                terrain_type="flatland",
                settlement_score=20,
            )
            hexes.append(hex_tile)
            session.add(hex_tile)
    session.commit()
    return hexes


@pytest.fixture
def unit_types(session):
    """Create standard unit types."""
    infantry = UnitType(
        name="Heavy Infantry",
        category="infantry",
        battle_multiplier=1.5,
        supply_cost_per_day=1,
        can_travel_offroad=True,
        special_abilities=None,
    )
    cavalry = UnitType(
        name="Heavy Cavalry",
        category="cavalry",
        battle_multiplier=4.0,
        supply_cost_per_day=10,
        can_travel_offroad=True,
        special_abilities=None,
    )
    skirmisher = UnitType(
        name="Skirmishers",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
        special_abilities={"skirmisher": True},
    )
    session.add(infantry)
    session.add(cavalry)
    session.add(skirmisher)
    session.commit()
    return {"infantry": infantry, "cavalry": cavalry, "skirmisher": skirmisher}


@pytest.fixture
def traits(session):
    """Create standard traits."""
    logistician = Trait(
        name="Logistician",
        description="+20% supply capacity, half column length",
        scope_tags=["logistics_mod"],
        effect_data={"supply_capacity_multiplier": 1.2, "column_length_multiplier": 0.5},
    )
    spartan = Trait(
        name="Spartan",
        description="Half noncombatants",
        scope_tags=["logistics_mod"],
        effect_data={"noncombatant_percentage": 0.125},
    )
    session.add(logistician)
    session.add(spartan)
    session.commit()
    return {"logistician": logistician, "spartan": spartan}


def test_complete_army_lifecycle(session, game, faction, hex_map, unit_types):
    """Test complete army lifecycle: create, update, split, merge."""
    # Create commander
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="General Marcus",
        age=40,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.commit()

    # Create army with multiple detachments
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det1 = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="1st Legion",
        soldier_count=5000,
        wagon_count=50,
        formation_position=0,
    )
    det2 = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["cavalry"].id,
        name="1st Cavalry Wing",
        soldier_count=2000,
        wagon_count=20,
        formation_position=1,
    )
    det3 = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="2nd Legion",
        soldier_count=5000,
        wagon_count=50,
        formation_position=2,
    )
    session.add_all([det1, det2, det3])
    session.commit()

    # Update composition
    update_army_composition(army, session)
    session.refresh(army)

    # Verify composition
    assert army.noncombatant_count == 3000  # 25% of 12000
    assert army.supplies_capacity > 0
    assert army.daily_supply_consumption > 0

    # Validate
    is_valid, error = validate_army_composition(army)
    assert is_valid is True
    assert error is None

    # Create second commander for split
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="General Scipio",
        age=35,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander2)
    session.commit()

    # Split army
    new_army = split_army(army, commander2.id, [det3.id], session)
    session.refresh(army)
    session.refresh(new_army)

    assert len(army.detachments) == 2
    assert len(new_army.detachments) == 1

    # Merge back together
    merge_armies(army, new_army, session)
    session.refresh(army)

    assert len(army.detachments) == 3


def test_army_with_logistician_trait(  # noqa: PLR0913
    session, game, faction, hex_map, unit_types, traits
):
    """Test army with Logistician trait modifiers."""
    # Create commander with Logistician trait
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Logistics Master",
        age=45,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.flush()

    commander_trait = CommanderTrait(
        commander_id=commander.id,
        trait_id=traits["logistician"].id,
        acquired_at_age=30,
    )
    session.add(commander_trait)
    session.commit()

    # Create army
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Efficient Legion",
        soldier_count=10000,
        wagon_count=100,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # Update composition (should use Logistician bonuses)
    update_army_composition(army, session)
    session.refresh(army)

    # Calculate expected values
    base_capacity = (10000 + 2500) * 15 + 100 * 1000  # Without Logistician
    expected_capacity = int(base_capacity * 1.2)  # With Logistician

    base_column = (10000 + 2500) / 5000.0  # 2.5 miles
    expected_column = base_column / 2.0  # 1.25 miles with Logistician

    assert army.supplies_capacity == expected_capacity
    assert army.column_length_miles == expected_column


def test_army_with_spartan_trait(  # noqa: PLR0913
    session, game, faction, hex_map, unit_types, traits
):
    """Test army with Spartan trait (reduced noncombatants)."""
    # Create commander with Spartan trait
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Spartan King",
        age=40,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.flush()

    commander_trait = CommanderTrait(
        commander_id=commander.id,
        trait_id=traits["spartan"].id,
        acquired_at_age=20,
    )
    session.add(commander_trait)
    session.commit()

    # Create army
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Spartan Hoplites",
        soldier_count=8000,
        wagon_count=80,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # Update composition
    update_army_composition(army, session)
    session.refresh(army)

    # Spartan: 12.5% instead of 25%
    assert army.noncombatant_count == 1000  # 8000 * 0.125


def test_exclusive_skirmisher_army_workflow(session, game, faction, hex_map, unit_types):
    """Test exclusive skirmisher army special rules."""
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Skirmish Master",
        age=30,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.commit()

    # Create exclusive skirmisher army (no wagons)
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det1 = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["skirmisher"].id,
        name="Light Skirmishers",
        soldier_count=2000,
        wagon_count=0,  # No wagons
        formation_position=0,
    )
    det2 = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["skirmisher"].id,
        name="Elite Skirmishers",
        soldier_count=1000,
        wagon_count=0,  # No wagons
        formation_position=1,
    )
    session.add_all([det1, det2])
    session.commit()

    # Update composition
    update_army_composition(army, session)
    session.refresh(army)

    # Should have 10% noncombatants (exclusive skirmisher rule)
    assert army.noncombatant_count == 300  # 3000 * 0.10

    # Should have exclusive_skirmisher flag
    assert army.status_effects is not None
    assert army.status_effects.get("exclusive_skirmisher") is True

    # Add wagons - should lose exclusive skirmisher status
    det1.wagon_count = 5
    session.commit()

    # Refresh before updating
    session.refresh(army)

    update_army_composition(army, session)
    session.refresh(army)

    # Should now have 25% noncombatants (default)
    assert army.noncombatant_count == 750  # 3000 * 0.25

    # Should NOT have exclusive_skirmisher flag (key should be removed or False)
    assert "exclusive_skirmisher" not in (army.status_effects or {})


def test_wizard_encumbrance(session, game, faction, hex_map, unit_types):
    """Test wizard detachments reduce supply capacity."""
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Wizard Commander",
        age=50,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.commit()

    # Create army with normal detachment
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det_infantry = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Guard Infantry",
        soldier_count=1000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det_infantry)
    session.commit()

    # Update and get baseline capacity
    update_army_composition(army, session)
    session.refresh(army)
    baseline_capacity = army.supplies_capacity

    # Add wizard detachment
    det_wizard = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Court Wizard",
        soldier_count=1,
        wagon_count=0,
        formation_position=1,
        instance_data={"supplies_equivalent": 1000},
    )
    session.add(det_wizard)
    session.commit()

    # Update with wizard
    update_army_composition(army, session)
    session.refresh(army)

    # Capacity should be reduced by 1000 (minus small addition from 1 soldier)
    assert army.supplies_capacity < baseline_capacity


def test_multi_army_supply_transfer(session, game, faction, hex_map, unit_types):
    """Test complex supply transfer scenario."""
    # Create two commanders
    commander1 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Supply Master",
        age=45,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Field Commander",
        age=35,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add_all([commander1, commander2])
    session.commit()

    # Create supply army (lots of wagons)
    supply_army = Army(
        game_id=game.id,
        commander_id=commander1.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(supply_army)
    session.flush()

    det_supply = Detachment(
        army_id=supply_army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Supply Train",
        soldier_count=500,
        wagon_count=200,  # Massive wagon train
        formation_position=0,
    )
    session.add(det_supply)
    session.commit()

    # Create combat army (minimal wagons)
    combat_army = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(combat_army)
    session.flush()

    det_combat1 = Detachment(
        army_id=combat_army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Combat Legion",
        soldier_count=8000,
        wagon_count=20,
        formation_position=0,
    )
    det_combat2 = Detachment(
        army_id=combat_army.id,
        unit_type_id=unit_types["cavalry"].id,
        name="Cavalry Wing",
        soldier_count=2000,
        wagon_count=10,
        formation_position=1,
    )
    session.add_all([det_combat1, det_combat2])
    session.commit()

    # Update both armies
    update_army_composition(supply_army, session)
    update_army_composition(combat_army, session)
    session.refresh(supply_army)
    session.refresh(combat_army)

    # Supply army should have high capacity from wagons
    assert supply_army.supplies_capacity > 200000

    # Load supply army with supplies
    supply_army.supplies_current = 150000
    session.commit()

    # Transfer supplies to combat army
    transfer_supplies(supply_army, combat_army, 50000, session)
    session.refresh(supply_army)
    session.refresh(combat_army)

    assert supply_army.supplies_current == 100000
    assert combat_army.supplies_current == 50000


def test_complex_army_split_and_merge(session, game, faction, hex_map, unit_types):
    """Test complex split and merge operations."""
    # Create main commander
    main_commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Main Commander",
        age=50,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(main_commander)
    session.commit()

    # Create large army
    army = Army(
        game_id=game.id,
        commander_id=main_commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
        supplies_current=50000,
    )
    session.add(army)
    session.flush()

    # Add multiple detachments
    detachments = []
    for i in range(5):
        det = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name=f"Legion {i + 1}",
            soldier_count=2000,
            wagon_count=20,
            formation_position=i,
        )
        detachments.append(det)
        session.add(det)
    session.commit()

    # Create subordinate commanders
    sub_commanders = []
    for i in range(2):
        cmd = Commander(
            game_id=game.id,
            faction_id=faction.id,
            name=f"Sub Commander {i + 1}",
            age=30 + i * 5,
            status="active",
            current_hex_id=hex_map[0].id,
        )
        sub_commanders.append(cmd)
        session.add(cmd)
    session.commit()

    # Split into three armies
    army2 = split_army(army, sub_commanders[0].id, [detachments[1].id, detachments[2].id], session)
    session.refresh(army)

    army3 = split_army(army, sub_commanders[1].id, [detachments[3].id], session)
    session.refresh(army)
    session.refresh(army2)

    # Verify splits
    assert len(army.detachments) == 2  # 0, 4
    assert len(army2.detachments) == 2  # 1, 2
    assert len(army3.detachments) == 1  # 3

    # Move army3 to same hex as army2
    army3.current_hex_id = army2.current_hex_id
    session.commit()

    # Merge army3 into army2
    merge_armies(army2, army3, session)
    session.refresh(army2)

    assert len(army2.detachments) == 3  # 1, 2, 3

    # Move army2 to same hex as army
    army2.current_hex_id = army.current_hex_id
    session.commit()

    # Merge everything back
    merge_armies(army, army2, session)
    session.refresh(army)

    assert len(army.detachments) == 5  # All back together


def test_undersupplied_army_lifecycle(session, game, faction, hex_map, unit_types):
    """Test army undersupplied status through various scenarios."""
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Struggling Commander",
        age=30,
        status="active",
        current_hex_id=hex_map[0].id,
    )
    session.add(commander)
    session.commit()

    # Create army
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_map[0].id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=unit_types["infantry"].id,
        name="Hungry Legion",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # Update composition
    update_army_composition(army, session)
    session.refresh(army)

    daily_consumption = army.daily_supply_consumption

    # Well supplied
    army.supplies_current = daily_consumption * 10
    army.days_without_supplies = 0
    session.commit()
    session.refresh(army)

    assert army.is_undersupplied is False

    # Insufficient supplies
    army.supplies_current = daily_consumption - 100
    session.commit()
    session.refresh(army)

    assert army.is_undersupplied is True

    # Days without supplies
    army.supplies_current = daily_consumption * 2
    army.days_without_supplies = 1
    session.commit()
    session.refresh(army)

    assert army.is_undersupplied is True
