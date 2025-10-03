"""Unit tests for Army Management Service.

Tests all army service functions including composition calculations,
supply management, and army operations.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.cataphract.domain.supply import (
    calculate_column_length,
    calculate_daily_consumption,
    calculate_noncombatant_count,
    calculate_supply_capacity,
    calculate_total_cavalry,
    calculate_total_soldiers,
    calculate_total_wagons,
    is_army_undersupplied,
)
from src.cataphract.models import (
    Army,
    Base,
    Commander,
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
        name="Test Game",
        start_date=date(2025, 1, 1),
        current_day=0,
        current_day_part="morning",
        tick_schedule="daily",
        map_width=10,
        map_height=10,
        season="spring",
        status="setup",
    )
    session.add(game)
    session.commit()
    return game


@pytest.fixture
def faction(session, game):
    """Create a test faction."""
    faction = Faction(
        game_id=game.id,
        name="Test Faction",
        description="A test faction",
        color="#FF0000",
        special_rules={},
        unique_units=[],
    )
    session.add(faction)
    session.commit()
    return faction


@pytest.fixture
def hex_tile(session, game):
    """Create a test hex."""
    hex_tile = Hex(
        game_id=game.id,
        q=0,
        r=0,
        terrain_type="flatland",
        settlement_score=20,
    )
    session.add(hex_tile)
    session.commit()
    return hex_tile


@pytest.fixture
def commander(session, game, faction, hex_tile):
    """Create a test commander."""
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Test Commander",
        age=30,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander)
    session.commit()
    return commander


@pytest.fixture
def infantry_type(session):
    """Create an infantry unit type."""
    unit_type = UnitType(
        name="Heavy Infantry",
        category="infantry",
        battle_multiplier=1.5,
        supply_cost_per_day=1,
        can_travel_offroad=True,
        special_abilities=None,
    )
    session.add(unit_type)
    session.commit()
    return unit_type


@pytest.fixture
def cavalry_type(session):
    """Create a cavalry unit type."""
    unit_type = UnitType(
        name="Heavy Cavalry",
        category="cavalry",
        battle_multiplier=4.0,
        supply_cost_per_day=10,
        can_travel_offroad=True,
        special_abilities=None,
    )
    session.add(unit_type)
    session.commit()
    return unit_type


@pytest.fixture
def skirmisher_type(session):
    """Create a skirmisher unit type."""
    unit_type = UnitType(
        name="Skirmishers",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
        special_abilities={
            "skirmisher": True,
            "acts_as_cavalry_for_scouting": True,
            "acts_as_cavalry_for_foraging": True,
            "acts_as_cavalry_for_fording": True,
        },
    )
    session.add(unit_type)
    session.commit()
    return unit_type


@pytest.fixture
def basic_army(session, game, commander, hex_tile, infantry_type):
    """Create a basic army with one infantry detachment."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det)
    session.commit()
    return army


# Test: calculate_total_soldiers


def test_calculate_total_soldiers_single_detachment(basic_army):
    """Test total soldiers with a single detachment."""
    assert calculate_total_soldiers(basic_army) == 5000


def test_calculate_total_soldiers_multiple_detachments(session, basic_army, cavalry_type):
    """Test total soldiers with multiple detachments."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    assert calculate_total_soldiers(basic_army) == 6000


def test_calculate_total_soldiers_empty_army(session, game, commander, hex_tile):
    """Test total soldiers with no detachments."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.commit()

    assert calculate_total_soldiers(army) == 0


# Test: calculate_total_cavalry


def test_calculate_total_cavalry_only_infantry(basic_army):
    """Test cavalry count with only infantry."""
    assert calculate_total_cavalry(basic_army) == 0


def test_calculate_total_cavalry_mixed_army(session, basic_army, cavalry_type):
    """Test cavalry count in mixed army."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    assert calculate_total_cavalry(basic_army) == 1000


def test_calculate_total_cavalry_multiple_cavalry_detachments(
    session, game, commander, hex_tile, cavalry_type
):
    """Test cavalry count with multiple cavalry detachments."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det1 = Detachment(
        army_id=army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=0,
    )
    det2 = Detachment(
        army_id=army.id,
        unit_type_id=cavalry_type.id,
        name="2nd Cavalry",
        soldier_count=500,
        wagon_count=3,
        formation_position=1,
    )
    session.add(det1)
    session.add(det2)
    session.commit()

    assert calculate_total_cavalry(army) == 1500


# Test: calculate_total_wagons


def test_calculate_total_wagons_single_detachment(basic_army):
    """Test wagon count with single detachment."""
    assert calculate_total_wagons(basic_army) == 10


def test_calculate_total_wagons_multiple_detachments(session, basic_army, cavalry_type):
    """Test wagon count with multiple detachments."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    assert calculate_total_wagons(basic_army) == 15


def test_calculate_total_wagons_no_wagons(session, game, commander, hex_tile, infantry_type):
    """Test wagon count with no wagons."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=0,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    assert calculate_total_wagons(army) == 0


# Test: calculate_noncombatant_count


def test_calculate_noncombatant_count_default(basic_army):
    """Test noncombatant count with default 25%."""
    # 5000 * 0.25 = 1250
    assert calculate_noncombatant_count(basic_army) == 1250


def test_calculate_noncombatant_count_with_spartan_trait(session, basic_army):
    """Test noncombatant count with Spartan trait (12.5%)."""
    spartan_trait = Trait(
        name="Spartan",
        description="Half noncombatants",
        scope_tags=["logistics_mod"],
        effect_data={"noncombatant_percentage": 0.125},
    )
    session.add(spartan_trait)
    session.commit()

    # 5000 * 0.125 = 625
    assert calculate_noncombatant_count(basic_army, [spartan_trait]) == 625


def test_calculate_noncombatant_count_exclusive_skirmishers(
    session, game, commander, hex_tile, skirmisher_type
):
    """Test noncombatant count for exclusive skirmisher army (10%)."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=skirmisher_type.id,
        name="Skirmishers",
        soldier_count=1000,
        wagon_count=0,  # No wagons for exclusive skirmisher benefits
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # 1000 * 0.10 = 100
    assert calculate_noncombatant_count(army) == 100


def test_calculate_noncombatant_count_skirmishers_with_wagons(
    session, game, commander, hex_tile, skirmisher_type
):
    """Test that skirmishers with wagons use default percentage."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=skirmisher_type.id,
        name="Skirmishers",
        soldier_count=1000,
        wagon_count=5,  # Wagons prevent exclusive skirmisher benefits
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # 1000 * 0.25 = 250 (default, not 10%)
    assert calculate_noncombatant_count(army) == 250


# Test: calculate_column_length


def test_calculate_column_length_infantry_dominated(basic_army):
    """Test column length dominated by infantry."""
    # 5000 infantry + 1250 NC = 6250 / 5000 = 1.25 miles
    assert calculate_column_length(basic_army) == 1.25


def test_calculate_column_length_cavalry_dominated(
    session, game, commander, hex_tile, cavalry_type
):
    """Test column length dominated by cavalry."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=4000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # 4000 cavalry / 2000 = 2.0 miles
    # 1000 NC / 5000 = 0.2 miles
    # 5 wagons / 50 = 0.1 miles
    # Max = 2.0 miles
    assert calculate_column_length(army) == 2.0


def test_calculate_column_length_wagon_dominated(session, game, commander, hex_tile, infantry_type):
    """Test column length dominated by wagons."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=infantry_type.id,
        name="Supply Train",
        soldier_count=100,
        wagon_count=200,  # Massive wagon train
        formation_position=0,
    )
    session.add(det)
    session.commit()

    # 100 infantry + 25 NC = 125 / 5000 = 0.025 miles
    # 200 wagons / 50 = 4.0 miles
    # Max = 4.0 miles
    assert calculate_column_length(army) == 4.0


def test_calculate_column_length_with_logistician_trait(session, basic_army):
    """Test column length with Logistician trait (halved)."""
    logistician_trait = Trait(
        name="Logistician",
        description="Halves column length",
        scope_tags=["logistics_mod"],
        effect_data={"column_length_multiplier": 0.5},
    )
    session.add(logistician_trait)
    session.commit()

    # Normal: 1.25 miles, with Logistician: 0.625 miles
    assert calculate_column_length(basic_army, [logistician_trait]) == 0.625


# Test: calculate_supply_capacity


def test_calculate_supply_capacity_basic(basic_army):
    """Test basic supply capacity calculation."""
    # 5000 infantry * 15 = 75000
    # 1250 NC * 15 = 18750
    # 10 wagons * 1000 = 10000
    # Total = 103750
    assert calculate_supply_capacity(basic_army) == 103750


def test_calculate_supply_capacity_with_cavalry(session, basic_army, cavalry_type):
    """Test supply capacity with cavalry."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    # 5000 infantry * 15 = 75000
    # 1500 NC (25% of 6000) * 15 = 22500
    # 1000 cavalry * 75 = 75000
    # 15 wagons * 1000 = 15000
    # Total = 187500
    assert calculate_supply_capacity(basic_army) == 187500


def test_calculate_supply_capacity_with_logistician_trait(session, basic_army):
    """Test supply capacity with Logistician trait (+20%)."""
    logistician_trait = Trait(
        name="Logistician",
        description="+20% supply capacity",
        scope_tags=["logistics_mod"],
        effect_data={"supply_capacity_multiplier": 1.2},
    )
    session.add(logistician_trait)
    session.commit()

    # Base: 103750 * 1.20 = 124500
    assert calculate_supply_capacity(basic_army, [logistician_trait]) == 124500


def test_calculate_supply_capacity_with_wizard_detachment(session, basic_army, infantry_type):
    """Test supply capacity with wizard detachment (-1000 per wizard)."""
    # Get baseline capacity without wizard
    baseline_capacity = calculate_supply_capacity(basic_army)

    # Add wizard detachment
    wizard_det = Detachment(
        army_id=basic_army.id,
        unit_type_id=infantry_type.id,
        name="Wizard",
        soldier_count=1,
        wagon_count=0,
        formation_position=1,
        instance_data={"supplies_equivalent": 1000},
    )
    session.add(wizard_det)
    session.commit()

    # Refresh to get updated detachments
    session.refresh(basic_army)

    # Calculate new capacity with wizard
    # It should add capacity from 1 soldier but subtract 1000
    # Net effect should be close to baseline - 1000 + small addition from 1 soldier
    new_capacity = calculate_supply_capacity(basic_army)

    # The wizard encumbrance should reduce capacity significantly
    assert new_capacity < baseline_capacity


# Test: calculate_daily_consumption


def test_calculate_daily_consumption_infantry_only(basic_army):
    """Test daily consumption with only infantry."""
    # Set noncombatants first
    basic_army.noncombatant_count = 1250

    # 5000 infantry * 1 = 5000
    # 1250 NC * 1 = 1250
    # 10 wagons * 10 = 100
    # Total = 6350
    assert calculate_daily_consumption(basic_army) == 6350


def test_calculate_daily_consumption_with_cavalry(session, basic_army, cavalry_type):
    """Test daily consumption with cavalry."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    basic_army.noncombatant_count = 1500

    # 5000 infantry * 1 = 5000
    # 1500 NC * 1 = 1500
    # 1000 cavalry * 10 = 10000
    # 15 wagons * 10 = 150
    # Total = 16650
    assert calculate_daily_consumption(basic_army) == 16650


# Test: is_army_undersupplied


def test_is_army_undersupplied_sufficient_supplies(basic_army):
    """Test undersupplied flag when supplies are sufficient."""
    basic_army.supplies_current = 10000
    basic_army.daily_supply_consumption = 5000
    basic_army.days_without_supplies = 0

    assert is_army_undersupplied(basic_army) is False


def test_is_army_undersupplied_insufficient_supplies(basic_army):
    """Test undersupplied flag when supplies are insufficient."""
    basic_army.supplies_current = 3000
    basic_army.daily_supply_consumption = 5000
    basic_army.days_without_supplies = 0

    assert is_army_undersupplied(basic_army) is True


def test_is_army_undersupplied_days_without_supplies(basic_army):
    """Test undersupplied flag when days_without_supplies > 0."""
    basic_army.supplies_current = 10000
    basic_army.daily_supply_consumption = 5000
    basic_army.days_without_supplies = 1

    assert is_army_undersupplied(basic_army) is True


# Test: split_army


def test_split_army_basic(  # noqa: PLR0913
    session, basic_army, infantry_type, game, faction, hex_tile
):
    """Test basic army splitting."""
    # Add second detachment
    det2 = Detachment(
        army_id=basic_army.id,
        unit_type_id=infantry_type.id,
        name="2nd Infantry",
        soldier_count=3000,
        wagon_count=5,
        formation_position=1,
    )
    session.add(det2)
    session.commit()

    # Create second commander
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.commit()

    # Split army
    new_army = split_army(basic_army, commander2.id, [det2.id], session)

    # Verify split
    session.refresh(basic_army)
    session.refresh(new_army)

    assert len(basic_army.detachments) == 1
    assert len(new_army.detachments) == 1
    assert new_army.commander_id == commander2.id
    assert new_army.current_hex_id == basic_army.current_hex_id


def test_split_army_empty_detachments_raises_error(session, basic_army, game, faction, hex_tile):
    """Test that splitting with no detachments raises error."""
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.commit()

    with pytest.raises(ValueError, match="Must specify at least one detachment"):
        split_army(basic_army, commander2.id, [], session)


def test_split_army_all_detachments_raises_error(session, basic_army, game, faction, hex_tile):
    """Test that splitting all detachments raises error."""
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.commit()

    det_ids = [det.id for det in basic_army.detachments]

    with pytest.raises(ValueError, match="Cannot split all detachments"):
        split_army(basic_army, commander2.id, det_ids, session)


def test_split_army_invalid_detachment_id_raises_error(
    session, basic_army, game, faction, hex_tile
):
    """Test that splitting with invalid detachment ID raises error."""
    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.commit()

    with pytest.raises(ValueError, match="do not belong to this army"):
        split_army(basic_army, commander2.id, [99999], session)


# Test: merge_armies


def test_merge_armies_basic(  # noqa: PLR0913
    session, game, commander, hex_tile, infantry_type, cavalry_type
):
    """Test basic army merging."""
    # Create two armies
    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=1000,
    )
    session.add(army1)
    session.flush()

    det1 = Detachment(
        army_id=army1.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det1)

    # Create second commander and army
    commander2 = Commander(
        game_id=game.id,
        faction_id=commander.faction_id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.flush()

    army2 = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=500,
    )
    session.add(army2)
    session.flush()

    det2 = Detachment(
        army_id=army2.id,
        unit_type_id=cavalry_type.id,
        name="1st Cavalry",
        soldier_count=1000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det2)
    session.commit()

    # Merge army2 into army1
    merge_armies(army1, army2, session)

    # Verify merge
    session.refresh(army1)

    assert len(army1.detachments) == 2
    assert army1.supplies_current == 1500


def test_merge_armies_different_hex_raises_error(session, game, commander, infantry_type, faction):
    """Test that merging armies in different hexes raises error."""
    hex1 = Hex(game_id=game.id, q=10, r=10, terrain_type="flatland", settlement_score=20)
    hex2 = Hex(game_id=game.id, q=11, r=10, terrain_type="flatland", settlement_score=20)
    session.add(hex1)
    session.add(hex2)
    session.flush()

    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex1.id,
        status="idle",
    )
    session.add(army1)
    session.flush()

    det1 = Detachment(
        army_id=army1.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det1)

    commander2 = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex2.id,
    )
    session.add(commander2)
    session.flush()

    army2 = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex2.id,
        status="idle",
    )
    session.add(army2)
    session.flush()

    det2 = Detachment(
        army_id=army2.id,
        unit_type_id=infantry_type.id,
        name="2nd Infantry",
        soldier_count=3000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det2)
    session.commit()

    with pytest.raises(ValueError, match="must be in the same hex"):
        merge_armies(army1, army2, session)


# Test: transfer_supplies


def test_transfer_supplies_basic(session, game, commander, hex_tile, infantry_type):
    """Test basic supply transfer."""
    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=5000,
        supplies_capacity=10000,
    )
    session.add(army1)
    session.flush()

    det1 = Detachment(
        army_id=army1.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det1)

    commander2 = Commander(
        game_id=game.id,
        faction_id=commander.faction_id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.flush()

    army2 = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=1000,
        supplies_capacity=10000,
    )
    session.add(army2)
    session.flush()

    det2 = Detachment(
        army_id=army2.id,
        unit_type_id=infantry_type.id,
        name="2nd Infantry",
        soldier_count=3000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det2)
    session.commit()

    # Transfer supplies
    transfer_supplies(army1, army2, 2000, session)

    # Verify transfer
    session.refresh(army1)
    session.refresh(army2)

    assert army1.supplies_current == 3000
    assert army2.supplies_current == 3000


def test_transfer_supplies_insufficient_supplies_raises_error(
    session, game, commander, hex_tile, infantry_type
):
    """Test that transferring more than available raises error."""
    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=1000,
        supplies_capacity=10000,
    )
    session.add(army1)
    session.flush()

    det1 = Detachment(
        army_id=army1.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det1)

    commander2 = Commander(
        game_id=game.id,
        faction_id=commander.faction_id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.flush()

    army2 = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=0,
        supplies_capacity=10000,
    )
    session.add(army2)
    session.flush()

    det2 = Detachment(
        army_id=army2.id,
        unit_type_id=infantry_type.id,
        name="2nd Infantry",
        soldier_count=3000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det2)
    session.commit()

    with pytest.raises(ValueError, match="insufficient supplies"):
        transfer_supplies(army1, army2, 2000, session)


def test_transfer_supplies_exceeds_capacity_raises_error(
    session, game, commander, hex_tile, infantry_type
):
    """Test that transferring more than capacity raises error."""
    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=10000,
        supplies_capacity=10000,
    )
    session.add(army1)
    session.flush()

    det1 = Detachment(
        army_id=army1.id,
        unit_type_id=infantry_type.id,
        name="1st Infantry",
        soldier_count=5000,
        wagon_count=10,
        formation_position=0,
    )
    session.add(det1)

    commander2 = Commander(
        game_id=game.id,
        faction_id=commander.faction_id,
        name="Second Commander",
        age=35,
        status="active",
        current_hex_id=hex_tile.id,
    )
    session.add(commander2)
    session.flush()

    army2 = Army(
        game_id=game.id,
        commander_id=commander2.id,
        current_hex_id=hex_tile.id,
        status="idle",
        supplies_current=900,
        supplies_capacity=1000,
    )
    session.add(army2)
    session.flush()

    det2 = Detachment(
        army_id=army2.id,
        unit_type_id=infantry_type.id,
        name="2nd Infantry",
        soldier_count=3000,
        wagon_count=5,
        formation_position=0,
    )
    session.add(det2)
    session.commit()

    with pytest.raises(ValueError, match="does not have enough capacity"):
        transfer_supplies(army1, army2, 500, session)


# Test: update_army_composition


def test_update_army_composition_basic(session, basic_army):
    """Test update_army_composition updates all fields."""
    update_army_composition(basic_army, session)

    session.refresh(basic_army)

    assert basic_army.noncombatant_count == 1250
    assert basic_army.column_length_miles == 1.25
    assert basic_army.supplies_capacity == 103750
    assert basic_army.daily_supply_consumption > 0


def test_update_army_composition_caps_supplies(session, basic_army):
    """Test that update_army_composition caps supplies at capacity."""
    basic_army.supplies_current = 200000  # Exceeds capacity

    update_army_composition(basic_army, session)

    session.refresh(basic_army)

    assert basic_army.supplies_current == basic_army.supplies_capacity


def test_update_army_composition_exclusive_skirmishers(
    session, game, commander, hex_tile, skirmisher_type
):
    """Test update_army_composition sets exclusive_skirmisher flag."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.flush()

    det = Detachment(
        army_id=army.id,
        unit_type_id=skirmisher_type.id,
        name="Skirmishers",
        soldier_count=1000,
        wagon_count=0,
        formation_position=0,
    )
    session.add(det)
    session.commit()

    update_army_composition(army, session)

    session.refresh(army)

    assert army.status_effects is not None
    assert army.status_effects.get("exclusive_skirmisher") is True


# Test: validate_army_composition


def test_validate_army_composition_valid(basic_army):
    """Test validation of valid army composition."""
    basic_army.supplies_current = 1000
    basic_army.supplies_capacity = 10000

    is_valid, error = validate_army_composition(basic_army)

    assert is_valid is True
    assert error is None


def test_validate_army_composition_no_detachments(session, game, commander, hex_tile):
    """Test validation fails with no detachments."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        status="idle",
    )
    session.add(army)
    session.commit()

    is_valid, error = validate_army_composition(army)

    assert is_valid is False
    assert error is not None
    assert "at least one detachment" in error


def test_validate_army_composition_supplies_exceed_capacity(basic_army):
    """Test validation fails when supplies exceed capacity."""
    basic_army.supplies_current = 200000
    basic_army.supplies_capacity = 10000

    is_valid, error = validate_army_composition(basic_army)

    assert is_valid is False
    assert error is not None
    assert "exceed capacity" in error


def test_validate_army_composition_negative_soldiers(session, basic_army, infantry_type):
    """Test validation fails with negative soldier count."""
    det = Detachment(
        army_id=basic_army.id,
        unit_type_id=infantry_type.id,
        name="Bad Infantry",
        soldier_count=-100,
        wagon_count=0,
        formation_position=1,
    )
    session.add(det)
    session.commit()

    is_valid, error = validate_army_composition(basic_army)

    assert is_valid is False
    assert error is not None
    assert "negative soldier count" in error
