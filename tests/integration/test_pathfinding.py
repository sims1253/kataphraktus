"""Integration tests for pathfinding module.

Tests pathfinding against a real database with actual hex data, road edges,
and river crossings.
"""

import pytest
from sqlalchemy.orm import Session

from cataphract.database import get_session_factory
from cataphract.domain.pathfinding import (
    calculate_ford_delay,
    calculate_total_travel_time,
    can_army_travel_route,
    find_route,
    requires_river_crossing,
)
from cataphract.models.army import Army, Detachment, UnitType
from cataphract.models.commander import Commander
from cataphract.models.faction import Faction
from cataphract.models.game import Game
from cataphract.models.map import Hex, RiverCrossing, RoadEdge


@pytest.fixture
def db_session():
    """Create a database session for integration tests."""
    SessionLocal = get_session_factory()  # noqa: N806
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_game(db_session: Session):
    """Create a test game."""
    import uuid  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    game = Game(
        name=f"Test Pathfinding Game {uuid.uuid4().hex[:8]}",
        start_date=datetime.now(tz=UTC).date(),
        current_day=0,
        current_day_part="morning",
        tick_schedule="daily",
        map_width=20,
        map_height=20,
        season="spring",
        status="active",
    )
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)
    return game


@pytest.fixture
def test_hexes(db_session: Session, test_game: Game):
    """Create a grid of test hexes."""
    hexes = []

    # Create a 5x5 grid of hexes
    for q in range(5):
        for r in range(5):
            hex_obj = Hex(
                game_id=test_game.id,
                q=q,
                r=r,
                terrain_type="flatland",
                settlement_score=0,
                has_road=False,
                is_good_country=False,
            )
            db_session.add(hex_obj)
            hexes.append(hex_obj)

    db_session.commit()

    # Refresh all hexes to get their IDs
    for hex_obj in hexes:
        db_session.refresh(hex_obj)

    return hexes


@pytest.fixture
def unit_types(db_session: Session):
    """Get existing unit types from database."""
    infantry = db_session.query(UnitType).filter_by(name="infantry").first()
    cavalry = db_session.query(UnitType).filter_by(name="cavalry").first()
    return {"infantry": infantry, "cavalry": cavalry}


class TestPathfindingIntegration:
    """Integration tests for pathfinding with real database."""

    def test_find_route_adjacent_hexes_road(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test finding a route between adjacent hexes with a road."""
        # Get two adjacent hexes
        hex1 = test_hexes[0]  # (0, 0)
        hex2 = test_hexes[1]  # (0, 1)

        # Create a road between them
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        db_session.add(road)
        db_session.commit()

        # Find route
        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].from_hex_id == hex1.id
        assert route[0].to_hex_id == hex2.id
        assert route[0].is_road is True
        assert route[0].distance_miles == 6.0
        assert route[0].travel_time_hours == 12.0

    def test_find_route_adjacent_hexes_off_road(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test finding an off-road route between adjacent hexes."""
        hex1 = test_hexes[0]  # (0, 0)
        hex2 = test_hexes[1]  # (0, 1)

        # Don't create a road - should use off-road movement
        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=True,
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].is_road is False
        assert route[0].travel_time_hours == 24.0  # Slower off-road

    def test_find_route_multi_hex(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test finding a route across multiple hexes."""
        # Create a road path: (0,0) -> (1,0) -> (2,0)
        hex_00 = next(h for h in test_hexes if h.q == 0 and h.r == 0)
        hex_10 = next(h for h in test_hexes if h.q == 1 and h.r == 0)
        hex_20 = next(h for h in test_hexes if h.q == 2 and h.r == 0)

        # Create roads
        road1 = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex_00.id, hex_10.id),
            to_hex_id=max(hex_00.id, hex_10.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        road2 = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex_10.id, hex_20.id),
            to_hex_id=max(hex_10.id, hex_20.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        db_session.add_all([road1, road2])
        db_session.commit()

        # Find route
        route = find_route(
            session=db_session,
            start_hex_id=hex_00.id,
            end_hex_id=hex_20.id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        assert len(route) == 2
        assert all(leg.is_road for leg in route)
        assert route[0].from_hex_id == hex_00.id
        assert route[0].to_hex_id == hex_10.id
        assert route[1].from_hex_id == hex_10.id
        assert route[1].to_hex_id == hex_20.id

    def test_find_route_with_seasonal_modifier(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test that seasonal modifiers are applied in pathfinding."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        # Create road with winter modifier
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="minor",
            base_cost_hours=12.0,
            status="open",
            seasonal_modifiers={"winter": 2.0, "spring": 1.0},
        )
        db_session.add(road)
        db_session.commit()

        # Update game season to winter
        test_game.season = "winter"
        db_session.commit()

        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season="winter",
        )

        assert route is not None
        assert route[0].travel_time_hours == 24.0  # 12.0 * 2.0

    def test_find_route_closed_road(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test that closed roads are not used in pathfinding."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        # Create closed road
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="closed",
        )
        db_session.add(road)
        db_session.commit()

        # Should not find road route with allow_off_road=False
        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=False,
        )

        assert route is None

    def test_find_route_with_bridge(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test pathfinding with a bridge crossing."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        # Create road with bridge
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        bridge = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            crossing_type="bridge",
            bridge_capacity=10,
            status="open",
        )
        db_session.add_all([road, bridge])
        db_session.commit()

        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].requires_river_crossing is True
        assert route[0].crossing_type == "bridge"

    def test_find_route_with_ford(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test pathfinding with a ford crossing."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        # Create road with ford
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        ford = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            crossing_type="ford",
            ford_quality="easy",
            status="open",
        )
        db_session.add_all([road, ford])
        db_session.commit()

        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        assert route[0].requires_river_crossing is True
        assert route[0].crossing_type == "ford"
        assert route[0].crossing_delay_hours == 12.0  # Nominal ford delay

    def test_find_route_avoids_slow_ford_for_large_army(
        self,
        db_session: Session,
        test_game: Game,
        test_hexes: list[Hex],
        unit_types: dict,
    ):
        """Large armies should route around fords when delays are excessive."""
        faction = Faction(game_id=test_game.id, name="Ford Test Faction", color="#00AAFF")
        db_session.add(faction)
        db_session.commit()

        commander = Commander(
            game_id=test_game.id,
            faction_id=faction.id,
            name="Ford Test Commander",
            age=40,
            status="active",
        )
        db_session.add(commander)
        db_session.commit()

        start_hex = test_hexes[10]  # (2, 0)
        detour_hex = test_hexes[6]  # (1, 1)
        destination_hex = test_hexes[5]  # (1, 0)

        army = Army(
            game_id=test_game.id,
            commander_id=commander.id,
            current_hex_id=start_hex.id,
            status="idle",
            noncombatant_count=5000,
        )
        db_session.add(army)
        db_session.commit()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name="Heavy Infantry",
            soldier_count=10000,
            wagon_count=0,
            formation_position=0,
        )
        db_session.add(detachment)
        db_session.commit()
        db_session.refresh(army)

        # Direct road with ford (fast pavement but slow ford for large armies)
        direct_road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(start_hex.id, destination_hex.id),
            to_hex_id=max(start_hex.id, destination_hex.id),
            road_quality="major",
            base_cost_hours=9.0,
            status="open",
        )
        ford = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(start_hex.id, destination_hex.id),
            to_hex_id=max(start_hex.id, destination_hex.id),
            crossing_type="ford",
            ford_quality="easy",
            status="open",
        )

        # Detour roads without crossings
        road_start_detour = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(start_hex.id, detour_hex.id),
            to_hex_id=max(start_hex.id, detour_hex.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        road_detour_destination = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(detour_hex.id, destination_hex.id),
            to_hex_id=max(detour_hex.id, destination_hex.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )

        db_session.add_all(
            [
                direct_road,
                ford,
                road_start_detour,
                road_detour_destination,
            ]
        )
        db_session.commit()

        # Without army context, direct ford route is fastest
        route_without_army = find_route(
            session=db_session,
            start_hex_id=start_hex.id,
            end_hex_id=destination_hex.id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=False,
        )

        assert route_without_army is not None
        assert len(route_without_army) == 1
        assert route_without_army[0].requires_river_crossing is True
        assert calculate_total_travel_time(route_without_army, army, db_session) == pytest.approx(
            45.0
        )

        # With large army, pathfinding should avoid the ford
        route_with_army = find_route(
            session=db_session,
            start_hex_id=start_hex.id,
            end_hex_id=destination_hex.id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=False,
            army=army,
        )

        assert route_with_army is not None
        assert len(route_with_army) == 2
        assert all(leg.requires_river_crossing is False for leg in route_with_army)
        assert calculate_total_travel_time(route_with_army, army, db_session) == pytest.approx(24.0)

    def test_find_route_closed_ford(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test that closed fords are not used."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        ford = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            crossing_type="ford",
            ford_quality="easy",
            status="closed",
        )
        db_session.add(ford)
        db_session.commit()

        # Should use off-road route, not crossing the closed ford
        route = find_route(
            session=db_session,
            start_hex_id=hex1.id,
            end_hex_id=hex2.id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=True,
        )

        # Route should exist but without the river crossing
        assert route is not None
        assert not route[0].requires_river_crossing

    def test_requires_river_crossing_detection(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex]
    ):
        """Test detecting river crossings between hexes."""
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]

        # Create river crossing
        crossing = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            crossing_type="bridge",
            status="open",
        )
        db_session.add(crossing)
        db_session.commit()

        result = requires_river_crossing(
            session=db_session,
            from_hex_id=hex1.id,
            to_hex_id=hex2.id,
            game_id=test_game.id,
        )

        assert result is True


class TestArmyMovementValidation:
    """Integration tests for army movement validation."""

    def test_army_with_wagons_off_road(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex], unit_types: dict
    ):
        """Test that armies with wagons cannot travel off-road."""
        # Create faction and commander
        faction = Faction(game_id=test_game.id, name="Test Faction", color="#FF0000")
        db_session.add(faction)
        db_session.commit()

        commander = Commander(
            game_id=test_game.id,
            faction_id=faction.id,
            name="Test Commander",
            age=30,
            status="active",
        )
        db_session.add(commander)
        db_session.commit()

        # Create army with wagons
        army = Army(
            game_id=test_game.id,
            commander_id=commander.id,
            current_hex_id=test_hexes[0].id,
            status="idle",
            noncombatant_count=100,
        )
        db_session.add(army)
        db_session.commit()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name="Test Infantry",
            soldier_count=1000,
            wagon_count=10,
            formation_position=0,
        )
        db_session.add(detachment)
        db_session.commit()
        db_session.refresh(army)

        # Create off-road route
        route = find_route(
            session=db_session,
            start_hex_id=test_hexes[0].id,
            end_hex_id=test_hexes[1].id,
            game_id=test_game.id,
            current_season=test_game.season,
            allow_off_road=True,
        )

        assert route is not None
        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is False
        assert error == "Wagons cannot travel off-road"

    def test_army_with_wagons_on_road(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex], unit_types: dict
    ):
        """Test that armies with wagons can travel on roads."""
        # Create faction and commander
        faction = Faction(game_id=test_game.id, name="Test Faction 2", color="#00FF00")
        db_session.add(faction)
        db_session.commit()

        commander = Commander(
            game_id=test_game.id,
            faction_id=faction.id,
            name="Test Commander 2",
            age=30,
            status="active",
        )
        db_session.add(commander)
        db_session.commit()

        army = Army(
            game_id=test_game.id,
            commander_id=commander.id,
            current_hex_id=test_hexes[0].id,
            status="idle",
            noncombatant_count=100,
        )
        db_session.add(army)
        db_session.commit()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name="Test Infantry 2",
            soldier_count=1000,
            wagon_count=10,
            formation_position=0,
        )
        db_session.add(detachment)
        db_session.commit()
        db_session.refresh(army)

        # Create road
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        db_session.add(road)
        db_session.commit()

        route = find_route(
            session=db_session,
            start_hex_id=test_hexes[0].id,
            end_hex_id=test_hexes[1].id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is True
        assert error is None

    def test_ford_delay_calculation_integration(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex], unit_types: dict
    ):
        """Test ford delay calculation with real army data."""
        # Create faction and commander
        faction = Faction(game_id=test_game.id, name="Test Faction 3", color="#0000FF")
        db_session.add(faction)
        db_session.commit()

        commander = Commander(
            game_id=test_game.id,
            faction_id=faction.id,
            name="Test Commander 3",
            age=30,
            status="active",
        )
        db_session.add(commander)
        db_session.commit()

        # Create army with 10,000 infantry + 2,500 NC
        army = Army(
            game_id=test_game.id,
            commander_id=commander.id,
            current_hex_id=test_hexes[0].id,
            status="idle",
            noncombatant_count=2500,
        )
        db_session.add(army)
        db_session.commit()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name="Large Infantry",
            soldier_count=10000,
            wagon_count=0,
            formation_position=0,
        )
        db_session.add(detachment)
        db_session.commit()
        db_session.refresh(army)

        # Calculate delay: (10000 + 2500) / 5000 * 0.5 * 24 = 30 hours
        delay = calculate_ford_delay(army, db_session)

        assert delay == 30.0

    def test_total_travel_time_with_ford_integration(
        self, db_session: Session, test_game: Game, test_hexes: list[Hex], unit_types: dict
    ):
        """Test total travel time calculation with ford crossing."""
        # Create faction and commander
        faction = Faction(game_id=test_game.id, name="Test Faction 4", color="#FFFF00")
        db_session.add(faction)
        db_session.commit()

        commander = Commander(
            game_id=test_game.id,
            faction_id=faction.id,
            name="Test Commander 4",
            age=30,
            status="active",
        )
        db_session.add(commander)
        db_session.commit()

        army = Army(
            game_id=test_game.id,
            commander_id=commander.id,
            current_hex_id=test_hexes[0].id,
            status="idle",
            noncombatant_count=2500,
        )
        db_session.add(army)
        db_session.commit()

        detachment = Detachment(
            army_id=army.id,
            unit_type_id=unit_types["infantry"].id,
            name="Ford Crossing Infantry",
            soldier_count=10000,
            wagon_count=0,
            formation_position=0,
        )
        db_session.add(detachment)
        db_session.commit()
        db_session.refresh(army)

        # Create road with ford
        hex1 = test_hexes[0]
        hex2 = test_hexes[1]
        road = RoadEdge(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
        )
        ford = RiverCrossing(
            game_id=test_game.id,
            from_hex_id=min(hex1.id, hex2.id),
            to_hex_id=max(hex1.id, hex2.id),
            crossing_type="ford",
            ford_quality="easy",
            status="open",
        )
        db_session.add_all([road, ford])
        db_session.commit()

        route = find_route(
            session=db_session,
            start_hex_id=test_hexes[0].id,
            end_hex_id=test_hexes[1].id,
            game_id=test_game.id,
            current_season=test_game.season,
        )

        assert route is not None
        # 12 hours road + 30 hours ford delay = 42 hours
        total_time = calculate_total_travel_time(route, army, db_session)

        assert total_time == 42.0
