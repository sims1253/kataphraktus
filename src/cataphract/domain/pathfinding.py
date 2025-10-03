"""Pathfinding and route calculation for army movement.

This module implements Dijkstra pathfinding over the road graph system,
handling both road and off-road movement, seasonal modifiers, river crossings,
and movement validation.
"""

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from cataphract.domain.supply import detachment_has_ability
from cataphract.models.army import Army
from cataphract.models.map import Hex, RiverCrossing, RoadEdge
from cataphract.utils.hex_math import HexCoord, hex_neighbors

if TYPE_CHECKING:
    pass


class NoPathError(Exception):
    """Raised when no path exists between two hexes."""


@dataclass
class MovementLeg:
    """Represents a single leg of a movement route.

    Attributes:
        from_hex_id: Source hex ID
        to_hex_id: Destination hex ID
        distance_miles: Distance in miles (6 miles per hex)
        travel_time_hours: Time to traverse this leg in hours
        is_road: Whether this leg uses a road
        requires_river_crossing: Whether this leg crosses a river
        crossing_type: Type of crossing (bridge/ford/none)
        crossing_delay_hours: Additional delay for river crossing (if applicable)
    """

    from_hex_id: int
    to_hex_id: int
    distance_miles: float
    travel_time_hours: float
    is_road: bool
    requires_river_crossing: bool = False
    crossing_type: str | None = None
    crossing_delay_hours: float = 0.0
    ford_quality: str | None = None
    ford_delay_is_nominal: bool = False


NOMINAL_FORD_DELAY_HOURS = 12.0
ROAD_DAMAGED_TIME_MULTIPLIER = 2.0
FORD_QUALITY_TIME_MULTIPLIERS: dict[str, float] = {
    "easy": 1.0,
    "difficult": 1.5,
}


def find_route(  # noqa: PLR0912, PLR0913, PLR0915
    session: Session,
    start_hex_id: int,
    end_hex_id: int,
    game_id: int,
    current_season: str,
    allow_off_road: bool = True,
    army: Army | None = None,
) -> list[MovementLeg] | None:
    """Find the shortest time route between two hexes using Dijkstra's algorithm.

    Args:
        session: Database session
        start_hex_id: Starting hex ID
        end_hex_id: Destination hex ID
        game_id: Game ID for filtering roads and crossings
        current_season: Current season for applying seasonal modifiers
        allow_off_road: Whether to allow off-road movement (default True)
        army: Army used for ford delay calculations (optional)

    Returns:
        List of MovementLeg objects representing the route, or None if no path exists

    Raises:
        NoPathError: If no path exists between the hexes
    """
    # Load all hexes for this game into memory for coordinate lookups
    hexes = session.query(Hex).filter(Hex.game_id == game_id).all()
    hex_map = {h.id: h for h in hexes}
    coord_to_hex = {(h.q, h.r): h for h in hexes}

    if start_hex_id not in hex_map or end_hex_id not in hex_map:
        raise NoPathError(f"Start or end hex not found in game {game_id}")

    # Load all road edges for this game
    road_edges = (
        session.query(RoadEdge)
        .filter(
            RoadEdge.game_id == game_id,
            RoadEdge.status.in_(["open", "damaged"]),
        )
        .all()
    )

    # Build adjacency graph for roads (bidirectional)
    road_graph: dict[int, list[tuple[int, RoadEdge]]] = {}
    for edge in road_edges:
        if edge.from_hex_id not in road_graph:
            road_graph[edge.from_hex_id] = []
        if edge.to_hex_id not in road_graph:
            road_graph[edge.to_hex_id] = []

        road_graph[edge.from_hex_id].append((edge.to_hex_id, edge))
        road_graph[edge.to_hex_id].append((edge.from_hex_id, edge))

    # Load all river crossings for this game
    river_crossings_list = (
        session.query(RiverCrossing).filter(RiverCrossing.game_id == game_id).all()
    )

    # Build river crossing lookup (bidirectional)
    river_crossings: dict[tuple[int, int], RiverCrossing] = {}
    for crossing in river_crossings_list:
        river_crossings[(crossing.from_hex_id, crossing.to_hex_id)] = crossing
        river_crossings[(crossing.to_hex_id, crossing.from_hex_id)] = crossing

    # Dijkstra's algorithm
    # Priority queue: (total_time_hours, hex_id)
    pq: list[tuple[float, int]] = [(0.0, start_hex_id)]
    visited: set[int] = set()
    # Best time to reach each hex
    best_time: dict[int, float] = {start_hex_id: 0.0}
    # Previous hex in path: hex_id -> (prev_hex_id, MovementLeg)
    previous: dict[int, tuple[int, MovementLeg]] = {}

    if army is not None:
        base_ford_delay_hours = calculate_ford_delay(army, session)
    else:
        base_ford_delay_hours = NOMINAL_FORD_DELAY_HOURS

    while pq:
        current_time, current_hex_id = heappop(pq)

        if current_hex_id in visited:
            continue

        visited.add(current_hex_id)

        # Found destination
        if current_hex_id == end_hex_id:
            break

        current_hex = hex_map[current_hex_id]
        current_coord = HexCoord(q=current_hex.q, r=current_hex.r)

        # Get all neighbors (6 adjacent hexes)
        neighbor_coords = hex_neighbors(current_coord)

        for neighbor_coord in neighbor_coords:
            # Check if neighbor hex exists in the game
            if (neighbor_coord.q, neighbor_coord.r) not in coord_to_hex:
                continue

            neighbor_hex = coord_to_hex[(neighbor_coord.q, neighbor_coord.r)]
            neighbor_hex_id = neighbor_hex.id

            if neighbor_hex_id in visited:
                continue

            # Check if there's a road connection
            is_road = False
            road_edge = None
            if current_hex_id in road_graph:
                for connected_hex_id, edge in road_graph[current_hex_id]:
                    if connected_hex_id == neighbor_hex_id:
                        is_road = True
                        road_edge = edge
                        break

            # If off-road movement is not allowed and there's no road, skip
            if not allow_off_road and not is_road:
                continue

            # Calculate movement time
            distance_miles = 6.0  # Each hex is 6 miles

            if is_road and road_edge:
                # Use base_cost_hours from road edge
                travel_time_hours = road_edge.base_cost_hours

                if road_edge.status == "damaged":
                    travel_time_hours *= ROAD_DAMAGED_TIME_MULTIPLIER

                # Apply seasonal modifier if present
                if road_edge.seasonal_modifiers and current_season in road_edge.seasonal_modifiers:
                    modifier = road_edge.seasonal_modifiers[current_season]
                    travel_time_hours *= modifier
            else:
                # Off-road movement: 6 miles/day = 0.25 miles/hour (assuming 24 hours)
                # Actually, base is 6 miles/day on roads = 12 hours for 6 miles
                # Off-road is half speed, so 12 hours becomes 24 hours
                travel_time_hours = 24.0  # 6 miles at half speed

            # Check for river crossing
            crossing_delay_hours = 0.0
            crossing_type = None
            requires_crossing = False
            ford_quality_value: str | None = None
            ford_delay_is_nominal = False
            edge_key = (current_hex_id, neighbor_hex_id)

            if edge_key in river_crossings:
                crossing = river_crossings[edge_key]
                requires_crossing = True

                # Check crossing status and seasonal closures
                if crossing.status != "open":
                    continue  # Cannot use this crossing

                if (
                    crossing.seasonal_closures
                    and current_season in crossing.seasonal_closures
                    and crossing.seasonal_closures[current_season]
                ):
                    continue  # Crossing is closed this season

                crossing_type = crossing.crossing_type

                if crossing.crossing_type == "ford":
                    if crossing.ford_quality == "impassable":
                        continue

                    quality_modifier = FORD_QUALITY_TIME_MULTIPLIERS.get(
                        crossing.ford_quality or "easy",
                        1.0,
                    )
                    crossing_delay_hours = base_ford_delay_hours * quality_modifier
                    ford_quality_value = crossing.ford_quality
                    ford_delay_is_nominal = army is None
                elif crossing.crossing_type == "bridge":
                    # Bridges have minimal delay
                    crossing_delay_hours = 0.0
                elif crossing.crossing_type == "none":
                    # Cannot cross
                    continue

            total_edge_time = travel_time_hours + crossing_delay_hours

            # Check if this path is better
            new_time = current_time + total_edge_time

            if neighbor_hex_id not in best_time or new_time < best_time[neighbor_hex_id]:
                best_time[neighbor_hex_id] = new_time

                leg = MovementLeg(
                    from_hex_id=current_hex_id,
                    to_hex_id=neighbor_hex_id,
                    distance_miles=distance_miles,
                    travel_time_hours=travel_time_hours,
                    is_road=is_road,
                    requires_river_crossing=requires_crossing,
                    crossing_type=crossing_type,
                    crossing_delay_hours=crossing_delay_hours,
                    ford_quality=ford_quality_value,
                    ford_delay_is_nominal=ford_delay_is_nominal,
                )

                previous[neighbor_hex_id] = (current_hex_id, leg)
                heappush(pq, (new_time, neighbor_hex_id))

    # Reconstruct path
    if end_hex_id not in previous and end_hex_id != start_hex_id:
        return None  # No path found

    if end_hex_id == start_hex_id:
        return []  # Already at destination

    # Build route by backtracking
    route: list[MovementLeg] = []
    current = end_hex_id

    while current != start_hex_id:
        prev_hex_id, leg = previous[current]
        route.append(leg)
        current = prev_hex_id

    route.reverse()
    return route


def calculate_ford_delay(army: Army, session: Session) -> float:  # noqa: ARG001
    """Calculate ford crossing delay for an army in hours.

    Formula: (infantry + noncombatant) / 5000 * 0.5 days * 24 hours/day

    Args:
        army: Army crossing the ford
        session: Database session for querying detachments (unused but kept for API consistency)

    Returns:
        Delay in hours
    """
    slow_detachments = [
        detachment
        for detachment in army.detachments
        if detachment.unit_type.category != "cavalry"
        and not detachment_has_ability(detachment, "acts_as_cavalry_for_fording")
    ]

    if not slow_detachments:
        return 0.0

    total_infantry = sum(detachment.soldier_count for detachment in slow_detachments)
    infantry_nc_count = total_infantry + army.noncombatant_count
    column_miles_infantry_nc = infantry_nc_count / 5000.0

    # Delay: column_miles * 0.5 days * 24 hours/day
    return column_miles_infantry_nc * 0.5 * 24.0


def requires_river_crossing(
    session: Session, from_hex_id: int, to_hex_id: int, game_id: int
) -> bool:
    """Check if moving between two hexes requires a river crossing.

    Args:
        session: Database session
        from_hex_id: Source hex ID
        to_hex_id: Destination hex ID
        game_id: Game ID

    Returns:
        True if a river crossing exists between the hexes
    """
    # Normalize edge to canonical form
    from_id, to_id = RoadEdge.normalize_edge(from_hex_id, to_hex_id)

    crossing = (
        session.query(RiverCrossing)
        .filter(
            RiverCrossing.game_id == game_id,
            RiverCrossing.from_hex_id == from_id,
            RiverCrossing.to_hex_id == to_id,
        )
        .first()
    )

    return crossing is not None


def can_army_travel_route(route: list[MovementLeg], army: Army) -> tuple[bool, str | None]:
    """Validate if an army can travel a route.

    Checks:
    - Wagons cannot travel off-road
    - Wagons cannot ford rivers

    Args:
        route: List of movement legs
        army: Army attempting to travel

    Returns:
        Tuple of (can_travel, error_message)
    """
    # Check if army has wagons
    total_wagons = sum(d.wagon_count for d in army.detachments)

    if total_wagons == 0:
        return (True, None)  # No wagons, can travel anywhere

    # Check for off-road legs
    for leg in route:
        if not leg.is_road:
            return (False, "Wagons cannot travel off-road")

    # Check for ford crossings
    for leg in route:
        if leg.requires_river_crossing and leg.crossing_type == "ford":
            return (False, "Wagons cannot cross fords")

    return (True, None)


def calculate_total_travel_time(route: list[MovementLeg], army: Army, session: Session) -> float:
    """Calculate total travel time for a route with army-specific modifiers.

    Args:
        route: List of movement legs
        army: Army traveling the route
        session: Database session for querying army data

    Returns:
        Total travel time in hours
    """
    total_hours = 0.0

    for leg in route:
        leg_hours = leg.travel_time_hours

        if leg.requires_river_crossing:
            if leg.crossing_type == "ford":
                quality_modifier = FORD_QUALITY_TIME_MULTIPLIERS.get(
                    leg.ford_quality or "easy",
                    1.0,
                )

                if leg.crossing_delay_hours > 0 and not leg.ford_delay_is_nominal:
                    leg_hours += leg.crossing_delay_hours
                else:
                    ford_delay = calculate_ford_delay(army, session)
                    leg_hours += ford_delay * quality_modifier
            else:
                leg_hours += leg.crossing_delay_hours

        total_hours += leg_hours

    return total_hours
