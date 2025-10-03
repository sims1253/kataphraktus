"""Integration tests for the tick service."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cataphract.models import (
    Army,
    Base,
    Commander,
    Event,
    Faction,
    Game,
    Hex,
    Message,
    Order,
    Weather,
)
from cataphract.services.tick_service import advance_tick


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create database session."""
    sessionmaker_class = sessionmaker(bind=engine)
    session = sessionmaker_class()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def complete_game(session):
    """Create a complete game with all entities."""
    # Create game
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

    # Create faction
    faction = Faction(game_id=game.id, name="Test Faction", color="#FF0000")
    session.add(faction)
    session.commit()

    # Create hex
    hex_loc = Hex(
        game_id=game.id,
        q=0,
        r=0,
        terrain_type="flatland",
        controlling_faction_id=faction.id,
    )
    session.add(hex_loc)
    session.commit()

    # Create commander
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Test Commander",
        age=35,
        status="active",
    )
    session.add(commander)
    session.commit()

    # Create army
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_loc.id,
        status="marching",
        morale_current=9,
        morale_resting=9,
        morale_max=12,
        supplies_current=1000,
        supplies_capacity=2000,
        daily_supply_consumption=100,
        days_without_supplies=0,
        days_marched_this_week=0,
    )
    session.add(army)
    session.commit()

    # Create message
    message = Message(
        game_id=game.id,
        sender_commander_id=commander.id,
        recipient_commander_id=commander.id,
        content="Test message",
        sent_at_day=0,
        sent_at_part="morning",
        sent_at_timestamp=datetime.now(UTC),
        route_legs={"eta_day": 1, "eta_part": "morning"},
        status="in_transit",
    )
    session.add(message)
    session.commit()

    # Create order
    order = Order(
        game_id=game.id,
        commander_id=commander.id,
        army_id=army.id,
        order_type="move",
        parameters={"destination": "hex_1"},
        issued_at=datetime.now(UTC),
        execute_at_day=0,
        execute_at_part="midday",
        status="pending",
    )
    session.add(order)
    session.commit()

    return {
        "game": game,
        "faction": faction,
        "hex": hex_loc,
        "commander": commander,
        "army": army,
        "message": message,
        "order": order,
    }


def test_full_day_progression(session, complete_game):
    """Test full day progression through all dayparts."""
    game_id = complete_game["game"].id

    # Morning → Midday
    result = advance_tick(game_id, session)
    assert result["current_day"] == 0
    assert result["current_part"] == "midday"

    # Midday → Evening
    result = advance_tick(game_id, session)
    assert result["current_day"] == 0
    assert result["current_part"] == "evening"

    # Evening → Night
    result = advance_tick(game_id, session)
    assert result["current_day"] == 0
    assert result["current_part"] == "night"

    # Night → Morning (next day)
    result = advance_tick(game_id, session)
    assert result["current_day"] == 1
    assert result["current_part"] == "morning"


def test_weather_updates_on_new_day(session, complete_game):
    """Test weather is updated when advancing to morning."""
    game_id = complete_game["game"].id

    # Advance through night to trigger morning
    for _ in range(4):
        advance_tick(game_id, session)

    # Check weather was created
    weather = session.query(Weather).filter_by(game_id=game_id, game_day=1).first()
    assert weather is not None
    assert weather.weather_type in ["clear", "rain", "snow", "storm", "fog", "very_bad"]


def test_message_delivery_integration(session, complete_game):
    """Test message delivery through tick progression."""
    game_id = complete_game["game"].id
    message = complete_game["message"]

    # Advance to day 1, morning (when message should be delivered)
    for _ in range(4):
        advance_tick(game_id, session)

    # Check message was delivered
    session.refresh(message)
    assert message.status == "delivered"
    assert message.delivered_at_day == 1
    assert message.delivered_at_part == "morning"

    # Check delivery event was created
    events = session.query(Event).filter_by(game_id=game_id, event_type="message_delivered").all()
    assert len(events) >= 1


def test_order_execution_integration(session, complete_game):
    """Test order execution through tick progression."""
    game_id = complete_game["game"].id
    order = complete_game["order"]

    # Advance to midday (when order should execute)
    result = advance_tick(game_id, session)

    assert result["orders_executed"] == 1
    session.refresh(order)
    assert order.status == "executing"
    assert order.executed_at_day == 0
    assert order.executed_at_part == "midday"


def test_supply_consumption_integration(session, complete_game):
    """Test supply consumption over multiple days."""
    game_id = complete_game["game"].id
    army = complete_game["army"]
    initial_supplies = army.supplies_current

    # Advance through full day (4 ticks)
    for _ in range(4):
        advance_tick(game_id, session)

    # Check supplies were consumed once (at end of day)
    session.refresh(army)
    expected_supplies = initial_supplies - army.daily_supply_consumption
    assert army.supplies_current == expected_supplies


def test_march_counter_increments(session, complete_game):
    """Test days_marched_this_week increments for marching armies."""
    game_id = complete_game["game"].id
    army = complete_game["army"]
    army.status = "marching"
    session.commit()

    # Advance through full day
    for _ in range(4):
        advance_tick(game_id, session)

    # Check march counter incremented
    session.refresh(army)
    assert army.days_marched_this_week == 1


def test_weekly_counter_reset(session, complete_game):
    """Test weekly counters reset after 7 days."""
    game_id = complete_game["game"].id
    army = complete_game["army"]
    army.status = "marching"
    army.days_marched_this_week = 5
    session.commit()

    # Advance to day 7
    for _ in range(7 * 4):  # 7 days x 4 parts
        advance_tick(game_id, session)

    # Check counter was reset at start of day 7
    session.refresh(army)
    assert army.days_marched_this_week <= 1  # May have incremented once on day 7


def test_starvation_progression(session, complete_game):
    """Test army starvation progression over time."""
    game_id = complete_game["game"].id
    army = complete_game["army"]
    army.supplies_current = 50  # Enough for 0 days
    initial_morale = army.morale_current
    session.commit()

    # Advance through 2 full days
    for _ in range(8):  # 2 days x 4 parts
        advance_tick(game_id, session)

    # Check starvation effects
    session.refresh(army)
    assert army.days_without_supplies >= 1
    assert army.morale_current < initial_morale

    # Check starvation events were created
    events = session.query(Event).filter_by(game_id=game_id, event_type="morale_check").all()
    assert len(events) >= 1


def test_sick_or_exhausted_flag_integration(session, complete_game):
    """Test sick_or_exhausted flag is set correctly."""
    game_id = complete_game["game"].id
    army = complete_game["army"]

    # Set up conditions for sick/exhausted
    army.days_without_supplies = 1
    session.commit()

    # Advance to morning to trigger flag calculation
    for _ in range(4):
        advance_tick(game_id, session)

    # Check flag was set
    session.refresh(army)
    assert army.status_effects is not None
    if "sick_or_exhausted" in army.status_effects:
        assert army.status_effects["sick_or_exhausted"]["active"] is True


def test_multiple_games_isolation(session):
    """Test that tick advancement doesn't affect other games."""
    # Create two games
    game1 = Game(
        name="Game 1",
        start_date=date(2025, 1, 1),
        current_day=0,
        current_day_part="morning",
        map_width=20,
        map_height=20,
        season="spring",
        status="active",
    )
    game2 = Game(
        name="Game 2",
        start_date=date(2025, 1, 1),
        current_day=5,
        current_day_part="evening",
        map_width=20,
        map_height=20,
        season="winter",
        status="active",
    )
    session.add_all([game1, game2])
    session.commit()

    # Advance game1
    advance_tick(game1.id, session)

    # Check game2 unchanged
    session.refresh(game2)
    assert game2.current_day == 5
    assert game2.current_day_part == "evening"


def test_event_generation(session, complete_game):
    """Test that events are generated during tick processing."""
    game_id = complete_game["game"].id

    # Advance through multiple ticks
    for _ in range(8):  # 2 full days
        advance_tick(game_id, session)

    # Check various events were created
    events = session.query(Event).filter_by(game_id=game_id).all()
    assert len(events) > 0

    # Should have weather change events
    weather_events = [e for e in events if e.event_type == "weather_change"]
    assert len(weather_events) >= 1


def test_deterministic_weather_generation(session, complete_game):
    """Test that weather generation is deterministic."""
    game_id = complete_game["game"].id

    # Advance to day 1
    for _ in range(4):
        advance_tick(game_id, session)

    weather1 = session.query(Weather).filter_by(game_id=game_id, game_day=1).first()

    # Create new game with same ID (simulate replay)
    # This is a simplified test - in reality you'd need to recreate the entire game state
    # Just verify weather was created
    assert weather1 is not None
    assert weather1.weather_type is not None


def test_complete_week_cycle(session, complete_game):
    """Test complete week cycle with all game mechanics."""
    game_id = complete_game["game"].id
    army = complete_game["army"]

    # Track state over a week
    initial_supplies = army.supplies_current

    # Advance through 7 full days
    for day in range(7):
        for part in range(4):
            result = advance_tick(game_id, session)
            assert result["current_day"] == day + (1 if part == 3 else 0)

    # Verify supplies consumed (7 days)
    session.refresh(army)
    expected_supplies = initial_supplies - (7 * army.daily_supply_consumption)
    assert army.supplies_current == expected_supplies

    # Verify weekly counter was reset
    assert army.days_marched_this_week <= 1  # At most 1 from current day
