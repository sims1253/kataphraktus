"""
Hexagonal coordinate system mathematics for Cataphract.

This module implements hex coordinate operations for the game's 6-mile hex map.
It supports:
- Distance calculations between hexes
- Finding adjacent hexes
- Finding all hexes within a range (for scouting, foraging, etc.)

Coordinate Systems:
-------------------
We use two coordinate systems:

1. Axial Coordinates (q, r) - for storage and representation
   - q: column coordinate
   - r: row coordinate
   - Compact: only 2 values needed
   - Used in HexCoord dataclass

2. Cube Coordinates (x, y, z) - for distance calculations
   - x, y, z: three coordinates with constraint x + y + z = 0
   - Makes distance calculation simple: max(|dx|, |dy|, |dz|)
   - Conversion: x = q, z = r, y = -x - z

References:
-----------
Based on the excellent guide at: https://www.redblobgames.com/grids/hexagons/
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HexCoord:
    """
    A hexagonal coordinate using axial coordinate system.

    Attributes:
        q: Column coordinate (horizontal axis)
        r: Row coordinate (diagonal axis)

    The axial coordinate system uses two coordinates (q, r) to uniquely
    identify each hex on the map. This is more compact than cube coordinates
    but requires conversion for distance calculations.

    Example:
        >>> origin = HexCoord(q=0, r=0)
        >>> neighbor = HexCoord(q=1, r=0)
        >>> hex_distance(origin, neighbor)
        1
    """

    q: int
    r: int

    def __hash__(self) -> int:
        """Make HexCoord hashable for use in sets and dicts."""
        return hash((self.q, self.r))


def axial_to_cube(coord: HexCoord) -> tuple[int, int, int]:
    """
    Convert axial coordinates (q, r) to cube coordinates (x, y, z).

    The conversion follows:
        x = q
        z = r
        y = -x - z

    This maintains the cube coordinate constraint: x + y + z = 0

    Args:
        coord: A hex coordinate in axial system

    Returns:
        A tuple (x, y, z) representing cube coordinates

    Example:
        >>> coord = HexCoord(q=1, r=2)
        >>> x, y, z = axial_to_cube(coord)
        >>> x, y, z
        (1, -3, 2)
        >>> x + y + z
        0
    """
    x = coord.q
    z = coord.r
    y = -x - z
    return x, y, z


def cube_to_axial(x: int, y: int, z: int) -> HexCoord:  # noqa: ARG001
    """
    Convert cube coordinates (x, y, z) back to axial coordinates (q, r).

    The conversion follows:
        q = x
        r = z

    Note: The y parameter is accepted for API consistency with cube coordinates,
    but is not used in the conversion as it's redundant (y = -x - z).

    Args:
        x: X coordinate in cube system
        y: Y coordinate in cube system (not used, but accepted for consistency)
        z: Z coordinate in cube system

    Returns:
        A HexCoord in axial system

    Example:
        >>> coord = cube_to_axial(x=1, y=-3, z=2)
        >>> coord.q, coord.r
        (1, 2)
    """
    return HexCoord(q=x, r=z)


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    """
    Calculate the distance between two hexes.

    The distance is the minimum number of hex steps to move from hex a to hex b.
    This uses cube coordinates for the calculation:
        distance = max(|dx|, |dy|, |dz|)

    where dx, dy, dz are the differences in cube coordinates.

    Args:
        a: First hex coordinate
        b: Second hex coordinate

    Returns:
        The distance between the two hexes (non-negative integer)

    Example:
        >>> origin = HexCoord(q=0, r=0)
        >>> hex_a = HexCoord(q=2, r=1)
        >>> hex_distance(origin, hex_a)
        3
    """
    # Convert to cube coordinates
    ax, ay, az = axial_to_cube(a)
    bx, by, bz = axial_to_cube(b)

    # Calculate differences
    dx = abs(ax - bx)
    dy = abs(ay - by)
    dz = abs(az - bz)

    # Distance is the maximum of the three differences
    return max(dx, dy, dz)


# Direction vectors for the 6 neighbors in axial coordinates
# These represent the relative positions of adjacent hexes
_NEIGHBOR_DIRECTIONS: list[tuple[int, int]] = [
    (1, 0),  # East
    (1, -1),  # Northeast
    (0, -1),  # Northwest
    (-1, 0),  # West
    (-1, 1),  # Southwest
    (0, 1),  # Southeast
]


def hex_neighbors(coord: HexCoord) -> list[HexCoord]:
    """
    Find all 6 adjacent hexes to the given hex.

    Every hex has exactly 6 neighbors in the directions:
    East, Northeast, Northwest, West, Southwest, Southeast.

    This is useful for:
    - Basic movement (1 hex)
    - Finding adjacent areas
    - Pathfinding algorithms

    Args:
        coord: The center hex coordinate

    Returns:
        A list of 6 HexCoord objects representing the neighbors

    Example:
        >>> origin = HexCoord(q=0, r=0)
        >>> neighbors = hex_neighbors(origin)
        >>> len(neighbors)
        6
        >>> HexCoord(q=1, r=0) in neighbors
        True
    """
    neighbors = []
    for dq, dr in _NEIGHBOR_DIRECTIONS:
        neighbor = HexCoord(q=coord.q + dq, r=coord.r + dr)
        neighbors.append(neighbor)
    return neighbors


def hexes_in_range(center: HexCoord, n: int) -> list[HexCoord]:
    """
    Find all hexes within range n of the center hex (inclusive).

    This returns all hexes where distance(center, hex) <= n.
    The number of hexes follows the formula: 3n^2 + 3n + 1

    This is useful for:
    - Scouting ranges (1-3 hexes)
    - Foraging areas (variable range)
    - Area of effect calculations
    - Visibility calculations

    Args:
        center: The center hex coordinate
        n: The maximum distance (range)

    Returns:
        A list of HexCoord objects within the range

    Raises:
        ValueError: If n is negative

    Example:
        >>> center = HexCoord(q=0, r=0)
        >>> hexes = hexes_in_range(center, n=1)
        >>> len(hexes)
        7
        >>> center in hexes
        True
    """
    if n < 0:
        msg = f"Range n must be non-negative, got {n}"
        raise ValueError(msg)

    # Convert center to cube coordinates
    cx, cy, cz = axial_to_cube(center)

    hexes = []

    # Iterate through all possible coordinates in the bounding box
    # For a range n, we need to check coordinates from -n to +n
    for dx in range(-n, n + 1):
        for dy in range(max(-n, -dx - n), min(n, -dx + n) + 1):
            dz = -dx - dy
            # Check if this offset is within range
            if max(abs(dx), abs(dy), abs(dz)) <= n:
                # Convert back to axial and add to results
                hex_coord = cube_to_axial(cx + dx, cy + dy, cz + dz)
                hexes.append(hex_coord)

    return hexes
