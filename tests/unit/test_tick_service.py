"""Unit tests for the tick service."""

from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cataphract.domain.morale_data import ForageResult, TorchResult
from cataphract.models import (
    Army,
    Base,
    Battle,
    Commander,
    Event,
    Faction,
    Game,
    Hex,
    Message,
    Order,
    Weather,
)
from cataphract.services.tick_service import (
    _calculate_sick_or_exhausted,
    _consume_supplies,
    _get_consecutive_bad_weather_days,
    _get_weather_effects,
    _get_weather_probabilities,
    _part_index,
    _process_message_deliveries,
    _process_scheduled_orders,
    _process_start_of_day_flags,
    _reset_weekly_counters,
    _resolve_battles,
    advance_tick,
    update_weather,
)


class FakeSupplyService:
    """Fake supply service for testing."""

    def __init__(self):
        self.consume_result = None  # Can be set in tests

    def consume_supplies(self, army: Army) -> dict:
        """Consume supplies for an army using actual logic.

        This implementation mimics the real SupplyService.consume_supplies behavior
        for testing purposes.
        """
        if self.consume_result:
            return self.consume_result

        # Default behavior: actual supply consumption logic
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
            if army.days_without_supplies >= 14:
                army.status = "routed"
        else:
            # Reset starvation counter if army has supplies
            army.days_without_supplies = 0

        result["resulting_supplies"] = army.supplies_current

        return result

    def forage(self, params):  # noqa: ARG002
        """Stub forage method to satisfy ISupplyService protocol."""
        return ForageResult(
            success=False, foraged_supplies=0, foraged_hexes=[], failed_hexes=[], events=[]
        )

    def torch(self, params):  # noqa: ARG002
        """Stub torch method to satisfy ISupplyService protocol."""
        return TorchResult(success=False, torched_hexes=[], failed_hexes=[], events=[])


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
def game(session):
    """Create test game."""
    game = Game(
        name="Test Game",
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
    """Create test faction."""
    faction = Faction(game_id=game.id, name="Test Faction", color="#FF0000")
    session.add(faction)
    session.commit()
    return faction


@pytest.fixture
def hex_location(session, game):
    """Create test hex."""
    hex_loc = Hex(
        game_id=game.id,
        q=0,
        r=0,
        terrain_type="flatland",
        controlling_faction_id=None,
    )
    session.add(hex_loc)
    session.commit()
    return hex_loc


@pytest.fixture
def commander(session, game, faction):
    """Create test commander."""
    commander = Commander(
        game_id=game.id,
        faction_id=faction.id,
        name="Test Commander",
        age=35,
        status="active",
    )
    session.add(commander)
    session.commit()
    return commander


@pytest.fixture
def army(session, game, commander, hex_location):
    """Create test army."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_location.id,
        status="idle",
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
    return army


def test_advance_tick_morning_to_midday(session, game):
    """Test advancing from morning to midday."""
    result = advance_tick(game.id, session)

    assert result["previous_day"] == 0
    assert result["previous_part"] == "morning"
    assert result["current_day"] == 0
    assert result["current_part"] == "midday"


def test_advance_tick_night_to_morning_increments_day(session, game):
    """Test advancing from night to morning increments day."""
    game.current_day_part = "night"
    session.commit()

    result = advance_tick(game.id, session)

    assert result["previous_day"] == 0
    assert result["previous_part"] == "night"
    assert result["current_day"] == 1
    assert result["current_part"] == "morning"


def test_advance_tick_full_cycle(session, game):
    """Test full daypart cycle."""
    parts = ["morning", "midday", "evening", "night"]
    for i, expected_part in enumerate(parts[1:], 1):
        result = advance_tick(game.id, session)
        assert result["current_part"] == expected_part
        if i < len(parts) - 1:
            assert result["current_day"] == 0


def test_update_weather_creates_weather_entry(session, game):
    """Test weather generation."""
    with patch("cataphract.services.tick_service.rng.random_int") as mock_rng:
        mock_rng.return_value = {"value": 30, "seed": "test"}

        weather = update_weather(game.id, 1, session)

        assert weather.game_id == game.id
        assert weather.game_day == 1
        assert weather.weather_type in ["clear", "rain", "snow", "storm", "fog", "very_bad"]
        assert "scouting_mod" in weather.effects


def test_update_weather_creates_event(session, game):
    """Test weather change creates event."""
    with patch("cataphract.services.tick_service.rng.random_int") as mock_rng:
        mock_rng.return_value = {"value": 30, "seed": "test"}

        update_weather(game.id, 1, session)

        events = session.query(Event).filter_by(event_type="weather_change").all()
        assert len(events) == 1
        assert events[0].game_day == 1


def test_process_start_of_day_flags(session, game, army):
    """Test start-of-day flag processing."""
    _process_start_of_day_flags(game.id, game.current_day, session)

    session.refresh(army)
    assert army.status_effects is not None


def test_calculate_sick_or_exhausted_starvation(session, army):
    """Test sick/exhausted calculation for starvation."""
    army.days_without_supplies = 2
    session.commit()

    result = _calculate_sick_or_exhausted(army, 5, session)

    assert result is not None
    assert result["reason"] == "starvation"


def test_calculate_sick_or_exhausted_forced_march(session, army):
    """Test sick/exhausted calculation for forced march."""
    army.status = "forced_march"
    army.days_marched_this_week = 4
    session.commit()

    result = _calculate_sick_or_exhausted(army, 5, session)

    assert result is not None
    assert result["reason"] == "forced_march_fatigue"


def test_calculate_sick_or_exhausted_battle(session, game, army, hex_location):
    """Test sick/exhausted calculation after battle."""
    # Create a dummy event for the battle
    event = Event(
        game_id=game.id,
        game_day=4,
        game_part="morning",
        timestamp=datetime.now(UTC),
        event_type="battle",
        involved_entities={},
        description="Test battle",
        details={},
        rand_source=None,
        visible_to=[],
    )
    session.add(event)
    session.flush()  # Get event.id

    battle = Battle(
        game_id=game.id,
        event_id=event.id,
        game_day=4,
        hex_id=hex_location.id,
        battle_type="field",
        attacker_side=[army.id],
        defender_side=[999],
        attacker_rolls={"roll": 10},
        defender_rolls={"roll": 8},
        victor_side="attacker",
        roll_difference=2,
        casualties={},
        morale_changes={},
    )
    session.add(battle)
    session.commit()

    result = _calculate_sick_or_exhausted(army, 5, session)

    assert result is not None
    assert result["reason"] == "fought_battle_yesterday"


def test_calculate_sick_or_exhausted_weather(session, game, army):
    """Test sick/exhausted calculation for bad weather."""
    # Create 2 days of bad weather (including current day 5)
    for day in [4, 5]:
        weather = Weather(
            game_id=game.id,
            game_day=day,
            weather_type="storm",
            effects={"scouting_mod": -2},
        )
        session.add(weather)
    session.commit()

    result = _calculate_sick_or_exhausted(army, 5, session)

    assert result is not None
    assert result["reason"] == "weather_exposure"


def test_get_consecutive_bad_weather_days(session, game):
    """Test consecutive bad weather days calculation."""
    # Create consecutive bad weather
    for day in [8, 9, 10]:
        weather = Weather(
            game_id=game.id,
            game_day=day,
            weather_type="very_bad",
            effects={},
        )
        session.add(weather)
    session.commit()

    count = _get_consecutive_bad_weather_days(game.id, 10, session)
    assert count == 3


def test_process_message_deliveries(session, game, commander):
    """Test message delivery processing."""
    msg = Message(
        game_id=game.id,
        sender_commander_id=commander.id,
        recipient_commander_id=commander.id,
        content="Test message",
        sent_at_day=0,
        sent_at_part="morning",
        sent_at_timestamp=datetime.now(UTC),
        route_legs={"eta_day": 1, "eta_part": "midday"},
        status="in_transit",
    )
    session.add(msg)
    session.commit()

    count = _process_message_deliveries(game.id, 1, "evening", session)
    session.commit()  # Commit changes made by helper function

    assert count == 1
    session.refresh(msg)
    assert msg.status == "delivered"
    assert msg.delivered_at_day == 1


def test_process_scheduled_orders(session, game, army, commander):
    """Test scheduled order processing."""
    order = Order(
        game_id=game.id,
        commander_id=commander.id,
        army_id=army.id,
        order_type="move",
        parameters={},
        issued_at=datetime.now(UTC),
        execute_at_day=1,
        execute_at_part="morning",
        status="pending",
    )
    session.add(order)
    session.commit()

    count = _process_scheduled_orders(game.id, 1, "morning", session)
    session.commit()  # Commit changes made by helper function

    assert count == 1
    session.refresh(order)
    assert order.status == "executing"


def test_resolve_battles_detects_collision(session, game, commander, hex_location):
    """Test battle detection for armies in same hex."""
    # Create two armies in same hex
    army1 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_location.id,
        status="idle",
        morale_current=9,
        morale_resting=9,
        supplies_current=1000,
        daily_supply_consumption=100,
    )
    army2 = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_location.id,
        status="idle",
        morale_current=9,
        morale_resting=9,
        supplies_current=1000,
        daily_supply_consumption=100,
    )
    session.add_all([army1, army2])
    session.commit()

    count = _resolve_battles(game.id, 1, "morning", session)

    assert count >= 1
    battles = session.query(Event).filter_by(event_type="battle").all()
    assert len(battles) >= 1


def test_consume_supplies_normal(session, game, army):
    """Test normal supply consumption."""
    initial_supplies = army.supplies_current
    supply_service = FakeSupplyService()

    _consume_supplies(game.id, 0, session, supply_service)
    session.commit()  # Commit changes made by helper function

    session.refresh(army)
    assert army.supplies_current == initial_supplies - army.daily_supply_consumption
    assert army.days_without_supplies == 0


def test_consume_supplies_starvation(session, game, army):
    """Test supply consumption leading to starvation."""
    army.supplies_current = 50
    session.commit()
    supply_service = FakeSupplyService()

    _consume_supplies(game.id, 0, session, supply_service)
    session.commit()  # Commit changes made by helper function

    session.refresh(army)
    assert army.supplies_current < 0
    assert army.days_without_supplies == 1
    assert army.morale_current == 8


def test_consume_supplies_dissolution(session, game, army):
    """Test army dissolution after 14 days without supplies."""
    army.days_without_supplies = 13
    army.supplies_current = 0
    session.commit()
    supply_service = FakeSupplyService()

    _consume_supplies(game.id, 0, session, supply_service)
    session.commit()  # Commit changes made by helper function

    session.refresh(army)
    assert army.days_without_supplies == 14
    assert army.status == "routed"


def test_reset_weekly_counters(session, game, army):
    """Test weekly counter reset."""
    army.days_marched_this_week = 5
    session.commit()

    _reset_weekly_counters(game.id, session)
    session.commit()  # Commit changes made by helper function

    session.refresh(army)
    assert army.days_marched_this_week == 0


def test_get_weather_probabilities():
    """Test weather probability lookup."""
    spring_probs = _get_weather_probabilities("spring")
    assert "clear" in spring_probs
    assert "rain" in spring_probs

    winter_probs = _get_weather_probabilities("winter")
    assert "snow" in winter_probs


def test_get_weather_effects():
    """Test weather effects lookup."""
    clear_effects = _get_weather_effects("clear")
    assert clear_effects["scouting_mod"] == 0
    assert clear_effects["movement_mod"] == 0

    storm_effects = _get_weather_effects("storm")
    assert storm_effects["scouting_mod"] == -2
    assert "battle_mod" in storm_effects


def test_part_index():
    """Test daypart index calculation."""
    assert _part_index("morning") == 0
    assert _part_index("midday") == 1
    assert _part_index("evening") == 2
    assert _part_index("night") == 3


def test_advance_tick_invalid_game(session):
    """Test advance_tick with invalid game ID."""
    with pytest.raises(ValueError, match="Game 999 not found"):
        advance_tick(999, session)


def test_update_weather_invalid_game(session):
    """Test update_weather with invalid game ID."""
    with pytest.raises(ValueError, match="Game 999 not found"):
        update_weather(999, 1, session)
