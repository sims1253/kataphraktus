"""Unit tests for pathfinding module.

Tests pathfinding algorithms, movement validation, and route calculation
in isolation using mock data.
"""

from unittest.mock import MagicMock, Mock

import pytest

from cataphract.domain.pathfinding import (
    MovementLeg,
    NoPathError,
    calculate_ford_delay,
    calculate_total_travel_time,
    can_army_travel_route,
    find_route,
    requires_river_crossing,
)
from cataphract.models.army import Army, Detachment, UnitType
from cataphract.models.map import Hex, RiverCrossing, RoadEdge


class TestMovementLeg:
    """Tests for MovementLeg dataclass."""

    def test_movement_leg_creation(self):
        """Test creating a MovementLeg."""
        leg = MovementLeg(
            from_hex_id=1,
            to_hex_id=2,
            distance_miles=6.0,
            travel_time_hours=12.0,
            is_road=True,
        )

        assert leg.from_hex_id == 1
        assert leg.to_hex_id == 2
        assert leg.distance_miles == 6.0
        assert leg.travel_time_hours == 12.0
        assert leg.is_road is True
        assert leg.requires_river_crossing is False
        assert leg.crossing_type is None
        assert leg.crossing_delay_hours == 0.0
        assert leg.ford_quality is None
        assert leg.ford_delay_is_nominal is False

    def test_movement_leg_with_crossing(self):
        """Test creating a MovementLeg with river crossing."""
        leg = MovementLeg(
            from_hex_id=1,
            to_hex_id=2,
            distance_miles=6.0,
            travel_time_hours=12.0,
            is_road=True,
            requires_river_crossing=True,
            crossing_type="ford",
            crossing_delay_hours=12.0,
        )

        assert leg.requires_river_crossing is True
        assert leg.crossing_type == "ford"
        assert leg.crossing_delay_hours == 12.0
        assert leg.ford_quality is None
        assert leg.ford_delay_is_nominal is False


class TestFindRoute:
    """Tests for find_route pathfinding function."""

    def test_find_route_no_path(self):
        """Test that find_route returns None when no path exists."""
        # Create mock session
        session = MagicMock()

        # Create two disconnected hexes
        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=10, r=10, terrain_type="flatland", settlement_score=0)

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],  # hexes query
            [],  # road_edges query
            [],  # river_crossings query
        ]

        # With allow_off_road=False and no roads, should return None
        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
            allow_off_road=False,
        )

        assert route is None

    def test_find_route_same_hex(self):
        """Test that find_route returns empty list when start equals end."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1],  # hexes query
            [],  # road_edges query
            [],  # river_crossings query
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=1,
            game_id=1,
            current_season="spring",
        )

        assert route == []

    def test_find_route_invalid_hex(self):
        """Test that find_route raises NoPathError for invalid hex IDs."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)

        session.query.return_value.filter.return_value.all.return_value = [hex1]

        with pytest.raises(NoPathError, match="Start or end hex not found"):
            find_route(
                session=session,
                start_hex_id=1,
                end_hex_id=999,  # Non-existent hex
                game_id=1,
                current_season="spring",
            )

    def test_find_route_direct_road(self):
        """Test finding a route with a direct road connection."""
        session = MagicMock()

        # Create two adjacent hexes
        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        # Create road edge between them
        road = RoadEdge(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
            seasonal_modifiers=None,
        )
        road.from_hex = hex1
        road.to_hex = hex2

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],  # hexes query
            [road],  # road_edges query
            [],  # river_crossings query
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].from_hex_id == 1
        assert route[0].to_hex_id == 2
        assert route[0].distance_miles == 6.0
        assert route[0].travel_time_hours == 12.0
        assert route[0].is_road is True

    def test_find_route_damaged_road_increases_time(self):
        """Damaged roads remain passable but cost additional time."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        road = RoadEdge(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            road_quality="major",
            base_cost_hours=12.0,
            status="damaged",
            seasonal_modifiers=None,
        )
        road.from_hex = hex1
        road.to_hex = hex2

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],
            [road],
            [],
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
        )

        assert route is not None
        assert route[0].travel_time_hours == 24.0

    def test_find_route_with_seasonal_modifier(self):
        """Test that seasonal modifiers are applied correctly."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        # Road with winter modifier
        road = RoadEdge(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
            seasonal_modifiers={"winter": 2.0, "spring": 1.5},
        )
        road.from_hex = hex1
        road.to_hex = hex2

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],
            [road],
            [],
        ]

        # Test winter modifier
        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="winter",
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].travel_time_hours == 24.0  # 12.0 * 2.0

    def test_find_route_difficult_ford_delay(self):
        """Fords with difficult quality apply additional delay."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        road = RoadEdge(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            road_quality="major",
            base_cost_hours=12.0,
            status="open",
            seasonal_modifiers=None,
        )
        road.from_hex = hex1
        road.to_hex = hex2

        ford = RiverCrossing(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            crossing_type="ford",
            ford_quality="difficult",
            status="open",
        )

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],
            [road],
            [ford],
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
        )

        assert route is not None
        assert route[0].crossing_type == "ford"
        assert route[0].crossing_delay_hours == pytest.approx(18.0)

    def test_find_route_impassable_ford_blocks_path(self):
        """Impassable fords should block traversal entirely."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        ford = RiverCrossing(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            crossing_type="ford",
            ford_quality="impassable",
            status="open",
        )

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],
            [],
            [ford],
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
            allow_off_road=True,
        )

        assert route is None

    def test_find_route_off_road(self):
        """Test finding an off-road route between adjacent hexes."""
        session = MagicMock()

        hex1 = Hex(id=1, game_id=1, q=0, r=0, terrain_type="flatland", settlement_score=0)
        hex2 = Hex(id=2, game_id=1, q=1, r=0, terrain_type="flatland", settlement_score=0)

        session.query.return_value.filter.return_value.all.side_effect = [
            [hex1, hex2],
            [],  # No roads
            [],
        ]

        route = find_route(
            session=session,
            start_hex_id=1,
            end_hex_id=2,
            game_id=1,
            current_season="spring",
            allow_off_road=True,
        )

        assert route is not None
        assert len(route) == 1
        assert route[0].is_road is False
        assert route[0].travel_time_hours == 24.0  # Off-road is slower


class TestRiverCrossing:
    """Tests for river crossing functionality."""

    def test_requires_river_crossing_true(self):
        """Test that requires_river_crossing detects a crossing."""
        session = MagicMock()

        crossing = RiverCrossing(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            crossing_type="bridge",
            status="open",
        )

        session.query.return_value.filter.return_value.first.return_value = crossing

        result = requires_river_crossing(session=session, from_hex_id=1, to_hex_id=2, game_id=1)

        assert result is True

    def test_requires_river_crossing_false(self):
        """Test that requires_river_crossing returns False when no crossing exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        result = requires_river_crossing(session=session, from_hex_id=1, to_hex_id=2, game_id=1)

        assert result is False

    def test_requires_river_crossing_normalized(self):
        """Test that requires_river_crossing normalizes edge IDs."""
        session = MagicMock()

        crossing = RiverCrossing(
            id=1,
            game_id=1,
            from_hex_id=1,
            to_hex_id=2,
            crossing_type="bridge",
            status="open",
        )

        session.query.return_value.filter.return_value.first.return_value = crossing

        # Should work regardless of order
        result = requires_river_crossing(session=session, from_hex_id=2, to_hex_id=1, game_id=1)

        assert result is True


class TestCanArmyTravelRoute:
    """Tests for can_army_travel_route validation."""

    def test_can_travel_no_wagons(self):
        """Test that armies without wagons can travel anywhere."""
        # Create army without wagons
        army = Mock(spec=Army)
        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.wagon_count = 0
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        # Off-road route
        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=24.0,
                is_road=False,
            )
        ]

        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is True
        assert error is None

    def test_cannot_travel_wagons_off_road(self):
        """Test that wagons cannot travel off-road."""
        army = Mock(spec=Army)
        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.wagon_count = 10
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=24.0,
                is_road=False,
            )
        ]

        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is False
        assert error == "Wagons cannot travel off-road"

    def test_cannot_travel_wagons_ford(self):
        """Test that wagons cannot cross fords."""
        army = Mock(spec=Army)
        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.wagon_count = 10
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
                requires_river_crossing=True,
                crossing_type="ford",
            )
        ]

        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is False
        assert error == "Wagons cannot cross fords"

    def test_can_travel_wagons_bridge(self):
        """Test that wagons can cross bridges."""
        army = Mock(spec=Army)
        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.wagon_count = 10
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
                requires_river_crossing=True,
                crossing_type="bridge",
            )
        ]

        can_travel, error = can_army_travel_route(route, army)

        assert can_travel is True
        assert error is None


class TestCalculateFordDelay:
    """Tests for calculate_ford_delay function."""

    def test_ford_delay_calculation(self):
        """Test ford delay calculation formula."""
        session = Mock()

        # Create mock army with 10,000 infantry + 2,500 NC
        army = Mock(spec=Army)
        army.noncombatant_count = 2500

        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.soldier_count = 10000
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        # Formula: (10000 + 2500) / 5000 * 0.5 days * 24 hours/day
        # = 2.5 * 0.5 * 24 = 30 hours
        delay = calculate_ford_delay(army, session)

        assert delay == 30.0

    def test_ford_delay_cavalry_excluded(self):
        """Test that cavalry is excluded from ford delay calculation."""
        session = Mock()

        army = Mock(spec=Army)
        army.noncombatant_count = 1000

        # Infantry detachment
        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"
        infantry_det = Mock(spec=Detachment)
        infantry_det.soldier_count = 5000
        infantry_det.unit_type = infantry_type

        # Cavalry detachment (should be excluded)
        cavalry_type = Mock(spec=UnitType)
        cavalry_type.category = "cavalry"
        cavalry_det = Mock(spec=Detachment)
        cavalry_det.soldier_count = 2000
        cavalry_det.unit_type = cavalry_type

        army.detachments = [infantry_det, cavalry_det]

        # Only infantry + NC: (5000 + 1000) / 5000 * 0.5 * 24 = 14.4 hours
        delay = calculate_ford_delay(army, session)

        assert abs(delay - 14.4) < 0.01  # Allow for floating point precision

    def test_ford_delay_skirmishers_count_as_cavalry(self):
        """Skirmisher detachments with fording ability should bypass delay."""
        session = Mock()

        army = Mock(spec=Army)
        army.noncombatant_count = 500

        skirmisher_type = Mock(spec=UnitType)
        skirmisher_type.category = "infantry"
        skirmisher_type.special_abilities = {"acts_as_cavalry_for_fording": True}

        skirmisher_det = Mock(spec=Detachment)
        skirmisher_det.soldier_count = 3000
        skirmisher_det.unit_type = skirmisher_type

        army.detachments = [skirmisher_det]

        delay = calculate_ford_delay(army, session)

        assert delay == 0.0

    def test_ford_delay_zero(self):
        """Test ford delay with no infantry."""
        session = Mock()

        army = Mock(spec=Army)
        army.noncombatant_count = 0
        army.detachments = []

        delay = calculate_ford_delay(army, session)

        assert delay == 0.0


class TestCalculateTotalTravelTime:
    """Tests for calculate_total_travel_time function."""

    def test_total_travel_time_no_crossings(self):
        """Test total travel time calculation without crossings."""
        session = Mock()

        army = Mock(spec=Army)
        army.detachments = []

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
            ),
            MovementLeg(
                from_hex_id=2,
                to_hex_id=3,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
            ),
        ]

        total_time = calculate_total_travel_time(route, army, session)

        assert total_time == 24.0

    def test_total_travel_time_with_ford(self):
        """Test total travel time with ford crossing delay."""
        session = Mock()

        army = Mock(spec=Army)
        army.noncombatant_count = 2500

        infantry_type = Mock(spec=UnitType)
        infantry_type.category = "infantry"

        detachment = Mock(spec=Detachment)
        detachment.soldier_count = 10000
        detachment.unit_type = infantry_type

        army.detachments = [detachment]

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
                requires_river_crossing=True,
                crossing_type="ford",
            ),
        ]

        # 12 hours travel + 30 hours ford delay = 42 hours
        total_time = calculate_total_travel_time(route, army, session)

        assert total_time == 42.0

    def test_total_travel_time_with_bridge(self):
        """Test that bridge crossings don't add delay."""
        session = Mock()

        army = Mock(spec=Army)
        army.detachments = []

        route = [
            MovementLeg(
                from_hex_id=1,
                to_hex_id=2,
                distance_miles=6.0,
                travel_time_hours=12.0,
                is_road=True,
                requires_river_crossing=True,
                crossing_type="bridge",
            ),
        ]

        total_time = calculate_total_travel_time(route, army, session)

        assert total_time == 12.0  # No ford delay for bridges
