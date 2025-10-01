"""Unit tests for SQLAlchemy models.

These tests verify that all models can be instantiated, relationships work,
constraints are enforced, and seed data loads correctly.
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.cataphract.models import (
    Army,
    Base,
    Commander,
    CommanderTrait,
    Detachment,
    Event,
    Faction,
    FactionRelation,
    Game,
    Hex,
    Message,
    Order,
    Player,
    RoadEdge,
    Stronghold,
    Trait,
    UnitType,
    Weather,
    seed_all_catalog_data,
    seed_traits,
    seed_unit_types,
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing and dispose it after use."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        try:
            Base.metadata.drop_all(engine)
        except Exception:
            pass
        engine.dispose()


@pytest.fixture
def session(engine):
    """Create a new database session for a test."""
    Session = sessionmaker(bind=engine)  # noqa: N806
    session = Session()
    yield session
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
def player(session):
    """Create a test player."""
    player = Player(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_referee=False,
    )
    session.add(player)
    session.commit()
    return player


@pytest.fixture
def hex_(session, game):
    """Create a test hex."""
    hex_ = Hex(
        game_id=game.id,
        q=0,
        r=0,
        terrain_type="flatland",
        is_good_country=False,
        has_road=False,
        settlement_score=20,
        foraging_times_remaining=5,
        is_torched=False,
    )
    session.add(hex_)
    session.commit()
    return hex_


@pytest.fixture
def hex_origin(session, game):
    """Create a test hex at origin."""
    hex_ = Hex(
        game_id=game.id,
        q=0,
        r=0,
        terrain_type="flatland",
        is_good_country=False,
        has_road=False,
        settlement_score=20,
        foraging_times_remaining=5,
        is_torched=False,
    )
    session.add(hex_)
    session.commit()
    return hex_


@pytest.fixture
def hex_east(session, game):
    """Create a test hex to the east."""
    hex_ = Hex(
        game_id=game.id,
        q=1,
        r=0,
        terrain_type="flatland",
        is_good_country=False,
        has_road=False,
        settlement_score=20,
        foraging_times_remaining=5,
        is_torched=False,
    )
    session.add(hex_)
    session.commit()
    return hex_


@pytest.fixture
def commander(session, game, faction, player, hex_):
    """Create a test commander."""
    commander = Commander(
        game_id=game.id,
        player_id=player.id,
        faction_id=faction.id,
        name="Test Commander",
        age=30,
        current_hex_id=hex_.id,
        status="active",
    )
    session.add(commander)
    session.commit()
    return commander


@pytest.fixture
def army(session, game, commander, hex_):
    """Create a test army."""
    army = Army(
        game_id=game.id,
        commander_id=commander.id,
        current_hex_id=hex_.id,
        status="idle",
    )
    session.add(army)
    session.commit()
    return army


@pytest.fixture
def unit_type_infantry(session):
    """Create infantry unit type for testing."""
    seed_unit_types(session)
    result = session.execute(select(UnitType).where(UnitType.name == "infantry"))
    return result.scalar_one()


@pytest.fixture
def unit_type_siege(session):
    """Create siege engines unit type for testing."""
    seed_unit_types(session)
    result = session.execute(select(UnitType).where(UnitType.name == "siege_engines"))
    return result.scalar_one()


class TestGameModel:
    """Tests for the Game model."""

    def test_create_game(self, session):
        """Test creating a game instance."""
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

        assert game.id is not None
        assert game.name == "Test Game"
        assert game.current_day == 0
        assert game.season == "spring"

    def test_game_unique_name(self, session, game):  # noqa: ARG002
        """Test that game names must be unique."""
        duplicate_game = Game(
            name="Test Game",
            start_date=date(2025, 1, 1),
            map_width=10,
            map_height=10,
            season="spring",
            status="setup",
        )
        session.add(duplicate_game)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_game_timestamps(self, session):
        """Test that timestamps are automatically set."""
        game = Game(
            name="Timestamp Test",
            start_date=date(2025, 1, 1),
            map_width=10,
            map_height=10,
            season="spring",
            status="setup",
        )
        session.add(game)
        session.commit()

        assert game.created_at is not None
        assert game.updated_at is not None


class TestHexModel:
    """Tests for the Hex model."""

    def test_create_hex(self, session, game):
        """Test creating a hex instance."""
        hex_ = Hex(
            game_id=game.id,
            q=0,
            r=0,
            terrain_type="flatland",
            is_good_country=False,
            has_road=False,
            foraging_times_remaining=5,
            is_torched=False,
        )
        session.add(hex_)
        session.commit()

        assert hex_.id is not None
        assert hex_.q == 0
        assert hex_.r == 0
        assert hex_.terrain_type == "flatland"

    def test_hex_unique_coordinates(self, session, game):
        """Test that hex coordinates must be unique per game."""
        hex1 = Hex(
            game_id=game.id,
            q=0,
            r=0,
            terrain_type="flatland",
            foraging_times_remaining=5,
            is_torched=False,
        )
        session.add(hex1)
        session.commit()

        hex2 = Hex(
            game_id=game.id,
            q=0,
            r=0,
            terrain_type="hills",
            foraging_times_remaining=5,
            is_torched=False,
        )
        session.add(hex2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_hex_relationship_to_game(self, session, game, hex_):  # noqa: ARG002
        """Test that hex has relationship to game."""
        assert hex_.game is not None
        assert hex_.game.id == game.id


class TestFactionModel:
    """Tests for the Faction model."""

    def test_create_faction(self, session, game):
        """Test creating a faction instance."""
        faction = Faction(
            game_id=game.id,
            name="Empire",
            description="The mighty empire",
            color="#FF0000",
            special_rules={"bonus": 1},
            unique_units=["knights"],
        )
        session.add(faction)
        session.commit()

        assert faction.id is not None
        assert faction.name == "Empire"

    def test_faction_relation(self, session, game):
        """Test creating faction relations."""
        faction1 = Faction(game_id=game.id, name="Empire", color="#FF0000")
        faction2 = Faction(game_id=game.id, name="Kingdom", color="#0000FF")
        session.add_all([faction1, faction2])
        session.commit()

        relation = FactionRelation(
            faction_id=faction1.id,
            other_faction_id=faction2.id,
            relation_type="allied",
            since_day=0,
        )
        session.add(relation)
        session.commit()

        assert relation.id is not None
        assert relation.relation_type == "allied"


class TestPlayerModel:
    """Tests for the Player model."""

    def test_create_player(self, session):
        """Test creating a player instance."""
        player = Player(
            username="testplayer",
            email="test@example.com",
            password_hash="hashed_password",
            is_referee=False,
        )
        session.add(player)
        session.commit()

        assert player.id is not None
        assert player.username == "testplayer"
        assert player.is_referee is False

    def test_player_unique_username(self, session, player):  # noqa: ARG002
        """Test that usernames must be unique."""
        duplicate_player = Player(
            username="testuser",
            email="different@example.com",
            password_hash="hashed_password",
        )
        session.add(duplicate_player)

        with pytest.raises(IntegrityError):
            session.commit()


class TestCommanderModel:
    """Tests for the Commander model."""

    def test_create_commander(self, session, game, faction, player, hex_):
        """Test creating a commander instance."""
        commander = Commander(
            game_id=game.id,
            player_id=player.id,
            faction_id=faction.id,
            name="General Marcus",
            age=35,
            current_hex_id=hex_.id,
            status="active",
        )
        session.add(commander)
        session.commit()

        assert commander.id is not None
        assert commander.name == "General Marcus"
        assert commander.age == 35

    def test_commander_relationships(self, session, commander, player, faction):  # noqa: ARG002
        """Test commander relationships."""
        assert commander.player.id == player.id
        assert commander.faction.id == faction.id


class TestTraitModel:
    """Tests for the Trait model."""

    def test_seed_traits(self, session):
        """Test seeding traits."""
        seed_traits(session)

        result = session.execute(select(Trait))
        traits = result.scalars().all()

        assert len(traits) == 20
        trait_names = [t.name for t in traits]
        assert "beloved" in trait_names
        assert "brutal" in trait_names
        assert "veteran" in trait_names

    def test_commander_traits(self, session, commander):
        """Test assigning traits to commanders."""
        # Seed traits first
        seed_traits(session)

        # Get a trait
        result = session.execute(select(Trait).where(Trait.name == "beloved"))
        trait = result.scalar_one()

        # Assign to commander
        commander_trait = CommanderTrait(
            commander_id=commander.id,
            trait_id=trait.id,
            acquired_at_age=25,
        )
        session.add(commander_trait)
        session.commit()

        assert commander_trait.id is not None
        assert len(commander.traits) == 1


class TestArmyModel:
    """Tests for the Army model."""

    def test_create_army(self, session, game, commander, hex_):
        """Test creating an army instance."""
        army = Army(
            game_id=game.id,
            commander_id=commander.id,
            current_hex_id=hex_.id,
            name="First Army",
            morale_current=9,
            morale_resting=9,
            morale_max=12,
            supplies_current=1000,
            supplies_capacity=2000,
            daily_supply_consumption=50,
            status="idle",
        )
        session.add(army)
        session.commit()

        assert army.id is not None
        assert army.name == "First Army"
        assert army.status == "idle"


class TestUnitTypeModel:
    """Tests for the UnitType model."""

    def test_seed_unit_types(self, session):
        """Test seeding unit types."""
        seed_unit_types(session)

        result = session.execute(select(UnitType))
        unit_types = result.scalars().all()

        assert len(unit_types) == 7
        unit_names = [u.name for u in unit_types]
        assert "infantry" in unit_names
        assert "cavalry" in unit_names
        assert "siege_engines" in unit_names

    def test_unit_type_properties(self, session):
        """Test unit type properties."""
        seed_unit_types(session)

        result = session.execute(select(UnitType).where(UnitType.name == "heavy_cavalry"))
        heavy_cav = result.scalar_one()

        assert heavy_cav.battle_multiplier == 4.0
        assert heavy_cav.supply_cost_per_day == 10
        assert heavy_cav.category == "cavalry"


class TestDetachmentModel:
    """Tests for the Detachment model."""

    def test_create_detachment(self, session, game, commander, hex_):
        """Test creating a detachment."""
        seed_unit_types(session)

        army = Army(
            game_id=game.id,
            commander_id=commander.id,
            current_hex_id=hex_.id,
            status="idle",
        )
        session.add(army)
        session.commit()

        result = session.execute(select(UnitType).where(UnitType.name == "infantry"))
        infantry = result.scalar_one()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=infantry.id,
            name="First Infantry",
            soldier_count=1000,
            formation_position=1,
        )
        session.add(detachment)
        session.commit()

        assert detachment.id is not None
        assert detachment.soldier_count == 1000

    def test_detachment_engine_count_validation(self, session, army, unit_type_siege):
        """Test that engine_count must be a multiple of 10."""
        # Valid: multiple of 10
        det1 = Detachment(
            army_id=army.id,
            unit_type_id=unit_type_siege.id,
            name="Siege Engines",
            soldier_count=0,
            engine_count=10,
            formation_position=1,
        )
        session.add(det1)
        session.commit()
        assert det1.engine_count == 10

        # Valid: 0 is technically allowed (empty detachment)
        det2 = Detachment(
            army_id=army.id,
            unit_type_id=unit_type_siege.id,
            name="Siege Engines 2",
            soldier_count=0,
            engine_count=0,
            formation_position=2,
        )
        session.add(det2)
        session.commit()

        # Invalid: not a multiple of 10
        with pytest.raises(ValueError, match="multiple of 10"):
            Detachment(
                army_id=army.id,
                unit_type_id=unit_type_siege.id,
                name="Siege Engines 3",
                soldier_count=0,
                engine_count=15,  # Invalid
                formation_position=3,
            )

        # Invalid: 5
        with pytest.raises(ValueError, match="multiple of 10"):
            Detachment(
                army_id=army.id,
                unit_type_id=unit_type_siege.id,
                name="Siege Engines 4",
                soldier_count=0,
                engine_count=5,
                formation_position=4,
            )

    def test_detachment_engine_count_none_allowed(self, session, army, unit_type_infantry):
        """Test that engine_count can be None for non-siege units."""
        det = Detachment(
            army_id=army.id,
            unit_type_id=unit_type_infantry.id,
            name="Infantry",
            soldier_count=1000,
            engine_count=None,
            formation_position=1,
        )
        session.add(det)
        session.commit()
        assert det.engine_count is None


class TestMessageModel:
    """Tests for the Message model."""

    def test_create_message(self, session, game, commander):
        """Test creating a message."""
        # Create another commander to send to
        result = session.execute(select(Faction).where(Faction.game_id == game.id))
        faction = result.scalar_one()

        commander2 = Commander(
            game_id=game.id,
            faction_id=faction.id,
            name="Commander 2",
            age=30,
            status="active",
        )
        session.add(commander2)
        session.commit()

        message = Message(
            game_id=game.id,
            sender_commander_id=commander.id,
            recipient_commander_id=commander2.id,
            content="Hello!",
            sent_at_day=0,
            sent_at_part="morning",
            sent_at_timestamp=datetime.now(UTC),
            route_legs={"legs": []},
            status="in_transit",
        )
        session.add(message)
        session.commit()

        assert message.id is not None
        assert message.status == "in_transit"


class TestOrderModel:
    """Tests for the Order model."""

    def test_create_order(self, session, game, commander, hex_):
        """Test creating an order."""
        army = Army(
            game_id=game.id,
            commander_id=commander.id,
            current_hex_id=hex_.id,
            status="idle",
        )
        session.add(army)
        session.commit()

        order = Order(
            game_id=game.id,
            commander_id=commander.id,
            army_id=army.id,
            order_type="move",
            parameters='{"destination_hex_id": 1}',
            issued_at=datetime.now(UTC),
            execute_at_day=1,
            execute_at_part="morning",
            status="pending",
        )
        session.add(order)
        session.commit()

        assert order.id is not None
        assert order.order_type == "move"


class TestEventModel:
    """Tests for the Event model."""

    def test_create_event(self, session, game):
        """Test creating an event."""
        event = Event(
            game_id=game.id,
            game_day=0,
            game_part="morning",
            timestamp=datetime.now(UTC),
            event_type="movement",
            involved_entities={"army_ids": [1]},
            description="Army moved",
            visible_to=[],
        )
        session.add(event)
        session.commit()

        assert event.id is not None
        assert event.event_type == "movement"


class TestStrongholdModel:
    """Tests for the Stronghold model."""

    def test_create_stronghold(self, session, game, faction, hex_):
        """Test creating a stronghold."""
        stronghold = Stronghold(
            game_id=game.id,
            name="Capital City",
            hex_id=hex_.id,
            type="city",
            controlling_faction_id=faction.id,
            defensive_bonus=4,
            base_threshold=15,
            current_threshold=15,
            gates_open=False,
            supplies_held=5000,
            loot_held=1000,
        )
        session.add(stronghold)
        session.commit()

        assert stronghold.id is not None
        assert stronghold.type == "city"


class TestWeatherModel:
    """Tests for the Weather model."""

    def test_create_weather(self, session, game):
        """Test creating weather."""
        weather = Weather(
            game_id=game.id,
            game_day=0,
            weather_type="clear",
            effects={"movement_modifier": 0},
        )
        session.add(weather)
        session.commit()

        assert weather.id is not None
        assert weather.weather_type == "clear"


class TestSeedData:
    """Tests for seed data functions."""

    def test_seed_all_catalog_data(self, session):
        """Test seeding all catalog data."""
        seed_all_catalog_data(session)

        # Check traits
        result = session.execute(select(Trait))
        traits = result.scalars().all()
        assert len(traits) == 20

        # Check unit types
        result = session.execute(select(UnitType))
        unit_types = result.scalars().all()
        assert len(unit_types) == 7

    def test_seed_idempotent(self, session):
        """Test that seeding is idempotent."""
        seed_all_catalog_data(session)
        seed_all_catalog_data(session)  # Should not fail or duplicate

        result = session.execute(select(Trait))
        traits = result.scalars().all()
        assert len(traits) == 20  # Still only 20, not 40


class TestRelationships:
    """Tests for model relationships."""

    def test_game_to_hexes(self, session, game, hex_):  # noqa: ARG002
        """Test game to hexes relationship."""
        assert len(game.hexes) > 0
        assert game.hexes[0].id == hex_.id

    def test_faction_to_commanders(self, session, faction, commander):  # noqa: ARG002
        """Test faction to commanders relationship."""
        assert len(faction.commanders) > 0
        assert faction.commanders[0].id == commander.id

    def test_commander_to_armies(self, session, game, commander, hex_):
        """Test commander to armies relationship."""
        army = Army(
            game_id=game.id,
            commander_id=commander.id,
            current_hex_id=hex_.id,
            status="idle",
        )
        session.add(army)
        session.commit()

        assert len(commander.armies) == 1
        assert commander.armies[0].id == army.id


class TestRoadEdgeModel:
    """Tests for the RoadEdge model."""

    def test_road_edge_canonical_ordering(self, session, game, hex_origin, hex_east):
        """Test that road edges enforce canonical ordering."""
        # Attempt to create edge in wrong order (should fail)
        road = RoadEdge(
            game_id=game.id,
            from_hex_id=hex_east.id,  # larger ID
            to_hex_id=hex_origin.id,  # smaller ID
            road_quality="major",
            base_cost_hours=1.0,
            status="open",
        )
        session.add(road)

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_road_edge_normalize_edge(self):
        """Test the normalize_edge helper function."""
        assert RoadEdge.normalize_edge(10, 5) == (5, 10)
        assert RoadEdge.normalize_edge(3, 7) == (3, 7)
        assert RoadEdge.normalize_edge(1, 1) == (1, 1)  # Same hex (edge case)

    def test_road_edge_no_duplicates(self, session, game, hex_origin, hex_east):
        """Test that duplicate edges are prevented."""
        from_id, to_id = RoadEdge.normalize_edge(hex_origin.id, hex_east.id)

        road1 = RoadEdge(
            game_id=game.id,
            from_hex_id=from_id,
            to_hex_id=to_id,
            road_quality="major",
            base_cost_hours=1.0,
            status="open",
        )
        session.add(road1)
        session.commit()

        # Try to add same edge again (should fail)
        road2 = RoadEdge(
            game_id=game.id,
            from_hex_id=from_id,
            to_hex_id=to_id,
            road_quality="minor",
            base_cost_hours=2.0,
            status="open",
        )
        session.add(road2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_road_edge_correct_order(self, session, game, hex_origin, hex_east):
        """Test creating road edge in correct order."""
        from_id, to_id = RoadEdge.normalize_edge(hex_origin.id, hex_east.id)

        road = RoadEdge(
            game_id=game.id,
            from_hex_id=from_id,
            to_hex_id=to_id,
            road_quality="major",
            base_cost_hours=1.0,
            status="open",
        )
        session.add(road)
        session.commit()

        assert road.id is not None
        assert road.from_hex_id < road.to_hex_id
