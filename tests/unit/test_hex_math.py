"""
Test suite for hex coordinate math operations.

This module tests the hexagonal coordinate system used in Cataphract.
The game uses 6-mile hexes, and this system supports:
- Axial coordinates (q, r) for storage
- Cube coordinates (x, y, z) for calculations
- Distance calculations
- Neighbor finding
- Range queries for scouting, foraging, etc.
"""

import pytest

from cataphract.utils.hex_math import (
    HexCoord,
    axial_to_cube,
    cube_to_axial,
    hex_distance,
    hex_neighbors,
    hexes_in_range,
)


class TestHexCoord:
    """Test the HexCoord dataclass."""

    def test_hex_coord_creation(self) -> None:
        """Test creating a hex coordinate."""
        coord = HexCoord(q=0, r=0)
        assert coord.q == 0
        assert coord.r == 0

    def test_hex_coord_equality(self) -> None:
        """Test hex coordinate equality."""
        coord1 = HexCoord(q=1, r=2)
        coord2 = HexCoord(q=1, r=2)
        coord3 = HexCoord(q=2, r=1)
        assert coord1 == coord2
        assert coord1 != coord3

    def test_hex_coord_negative(self) -> None:
        """Test hex coordinates can be negative."""
        coord = HexCoord(q=-1, r=-2)
        assert coord.q == -1
        assert coord.r == -2

    def test_hex_coord_hash(self) -> None:
        """Test hex coordinates can be hashed (for use in sets/dicts)."""
        coord1 = HexCoord(q=1, r=2)
        coord2 = HexCoord(q=1, r=2)
        coord_set = {coord1, coord2}
        assert len(coord_set) == 1


class TestCoordinateConversion:
    """Test conversion between axial and cube coordinates."""

    def test_axial_to_cube_origin(self) -> None:
        """Test conversion at origin."""
        coord = HexCoord(q=0, r=0)
        x, y, z = axial_to_cube(coord)
        assert x == 0
        assert y == 0
        assert z == 0

    def test_axial_to_cube_positive(self) -> None:
        """Test conversion with positive coordinates."""
        coord = HexCoord(q=1, r=2)
        x, y, z = axial_to_cube(coord)
        assert x == 1
        assert z == 2
        assert y == -3
        # Verify cube coordinate constraint: x + y + z = 0
        assert x + y + z == 0

    def test_axial_to_cube_negative(self) -> None:
        """Test conversion with negative coordinates."""
        coord = HexCoord(q=-1, r=-2)
        x, y, z = axial_to_cube(coord)
        assert x == -1
        assert z == -2
        assert y == 3
        assert x + y + z == 0

    def test_axial_to_cube_mixed(self) -> None:
        """Test conversion with mixed positive/negative coordinates."""
        coord = HexCoord(q=3, r=-1)
        x, y, z = axial_to_cube(coord)
        assert x == 3
        assert z == -1
        assert y == -2
        assert x + y + z == 0

    def test_cube_to_axial_origin(self) -> None:
        """Test conversion back to axial at origin."""
        coord = cube_to_axial(x=0, y=0, z=0)
        assert coord.q == 0
        assert coord.r == 0

    def test_cube_to_axial_positive(self) -> None:
        """Test conversion back to axial with positive values."""
        coord = cube_to_axial(x=1, y=-3, z=2)
        assert coord.q == 1
        assert coord.r == 2

    def test_cube_to_axial_negative(self) -> None:
        """Test conversion back to axial with negative values."""
        coord = cube_to_axial(x=-1, y=3, z=-2)
        assert coord.q == -1
        assert coord.r == -2

    def test_roundtrip_conversion(self) -> None:
        """Test that converting axial -> cube -> axial gives same result."""
        original = HexCoord(q=5, r=-3)
        x, y, z = axial_to_cube(original)
        result = cube_to_axial(x, y, z)
        assert result == original

    def test_roundtrip_multiple_coords(self) -> None:
        """Test roundtrip conversion for multiple coordinates."""
        test_coords = [
            HexCoord(q=0, r=0),
            HexCoord(q=1, r=1),
            HexCoord(q=-1, r=-1),
            HexCoord(q=10, r=-5),
            HexCoord(q=-7, r=3),
        ]
        for original in test_coords:
            x, y, z = axial_to_cube(original)
            result = cube_to_axial(x, y, z)
            assert result == original


class TestHexDistance:
    """Test distance calculations between hexes."""

    def test_distance_to_self(self) -> None:
        """Test distance from a hex to itself is 0."""
        coord = HexCoord(q=5, r=3)
        assert hex_distance(coord, coord) == 0

    def test_distance_origin_to_adjacent(self) -> None:
        """Test distance from origin to adjacent hex is 1."""
        origin = HexCoord(q=0, r=0)
        adjacent = HexCoord(q=1, r=0)
        assert hex_distance(origin, adjacent) == 1

    def test_distance_symmetric(self) -> None:
        """Test distance is symmetric: d(a,b) == d(b,a)."""
        hex_a = HexCoord(q=1, r=2)
        hex_b = HexCoord(q=4, r=-1)
        assert hex_distance(hex_a, hex_b) == hex_distance(hex_b, hex_a)

    def test_distance_horizontal(self) -> None:
        """Test distance along horizontal (q) axis."""
        hex_a = HexCoord(q=0, r=0)
        hex_b = HexCoord(q=3, r=0)
        assert hex_distance(hex_a, hex_b) == 3

    def test_distance_vertical(self) -> None:
        """Test distance along vertical (r) axis."""
        hex_a = HexCoord(q=0, r=0)
        hex_b = HexCoord(q=0, r=4)
        assert hex_distance(hex_a, hex_b) == 4

    def test_distance_diagonal(self) -> None:
        """Test distance along diagonal."""
        hex_a = HexCoord(q=0, r=0)
        hex_b = HexCoord(q=2, r=2)
        # In axial coords: q=2, r=2 -> cube: x=2, y=-4, z=2
        # Distance is max(|2|, |-4|, |2|) = 4
        assert hex_distance(hex_a, hex_b) == 4

    def test_distance_negative_coords(self) -> None:
        """Test distance with negative coordinates."""
        hex_a = HexCoord(q=-2, r=-3)
        hex_b = HexCoord(q=1, r=2)
        # Should correctly handle negative values
        # Cube: (-2, 5, -3) to (1, -3, 2)
        # Diff: |3|, |-8|, |5| -> max = 8
        assert hex_distance(hex_a, hex_b) == 8

    def test_distance_large_values(self) -> None:
        """Test distance with large coordinate values."""
        hex_a = HexCoord(q=0, r=0)
        hex_b = HexCoord(q=100, r=50)
        # x=100, y=-150, z=50
        # max(|100|, |-150|, |50|) = 150
        assert hex_distance(hex_a, hex_b) == 150

    def test_distance_known_values(self) -> None:
        """Test distance with known calculated values."""
        test_cases = [
            # (0,0) to (1,-1): cube (0,0,0) to (1,0,-1) -> max(1,0,1) = 1
            (HexCoord(q=0, r=0), HexCoord(q=1, r=-1), 1),
            # (2,0) to (-1,3): cube (2,-2,0) to (-1,-2,3) -> max(3,0,3) = 3
            (HexCoord(q=2, r=0), HexCoord(q=-1, r=3), 3),
            # (-2,1) to (1,-2): cube (-2,1,1) to (1,1,-2) -> max(3,0,3) = 3
            (HexCoord(q=-2, r=1), HexCoord(q=1, r=-2), 3),
        ]
        for hex_a, hex_b, expected_distance in test_cases:
            assert hex_distance(hex_a, hex_b) == expected_distance


class TestHexNeighbors:
    """Test finding adjacent hexes."""

    def test_neighbors_count(self) -> None:
        """Test that every hex has exactly 6 neighbors."""
        coord = HexCoord(q=0, r=0)
        neighbors = hex_neighbors(coord)
        assert len(neighbors) == 6

    def test_neighbors_unique(self) -> None:
        """Test that all neighbors are unique."""
        coord = HexCoord(q=5, r=3)
        neighbors = hex_neighbors(coord)
        assert len(neighbors) == len(set(neighbors))

    def test_neighbors_distance(self) -> None:
        """Test that all neighbors are exactly distance 1 away."""
        coord = HexCoord(q=0, r=0)
        neighbors = hex_neighbors(coord)
        for neighbor in neighbors:
            assert hex_distance(coord, neighbor) == 1

    def test_neighbors_origin(self) -> None:
        """Test the 6 neighbors of the origin hex."""
        origin = HexCoord(q=0, r=0)
        neighbors = hex_neighbors(origin)
        expected = {
            HexCoord(q=1, r=0),
            HexCoord(q=1, r=-1),
            HexCoord(q=0, r=-1),
            HexCoord(q=-1, r=0),
            HexCoord(q=-1, r=1),
            HexCoord(q=0, r=1),
        }
        assert set(neighbors) == expected

    def test_neighbors_positive_coords(self) -> None:
        """Test neighbors of a hex with positive coordinates."""
        coord = HexCoord(q=2, r=3)
        neighbors = hex_neighbors(coord)
        expected = {
            HexCoord(q=3, r=3),
            HexCoord(q=3, r=2),
            HexCoord(q=2, r=2),
            HexCoord(q=1, r=3),
            HexCoord(q=1, r=4),
            HexCoord(q=2, r=4),
        }
        assert set(neighbors) == expected

    def test_neighbors_negative_coords(self) -> None:
        """Test neighbors with negative coordinates."""
        coord = HexCoord(q=-1, r=-1)
        neighbors = hex_neighbors(coord)
        # All should be distance 1
        for neighbor in neighbors:
            assert hex_distance(coord, neighbor) == 1

    def test_neighbor_reciprocity(self) -> None:
        """Test that if B is a neighbor of A, then A is a neighbor of B."""
        hex_a = HexCoord(q=3, r=-2)
        neighbors_a = hex_neighbors(hex_a)
        for hex_b in neighbors_a:
            neighbors_b = hex_neighbors(hex_b)
            assert hex_a in neighbors_b


class TestHexesInRange:
    """Test finding all hexes within a given range."""

    def test_range_zero(self) -> None:
        """Test range 0 returns only the center hex."""
        center = HexCoord(q=5, r=3)
        hexes = hexes_in_range(center, n=0)
        assert len(hexes) == 1
        assert center in hexes

    def test_range_one(self) -> None:
        """Test range 1 returns center plus 6 neighbors."""
        center = HexCoord(q=0, r=0)
        hexes = hexes_in_range(center, n=1)
        # 1 center + 6 neighbors = 7
        assert len(hexes) == 7
        assert center in hexes

    def test_range_one_correct_hexes(self) -> None:
        """Test range 1 returns the correct hexes."""
        center = HexCoord(q=0, r=0)
        hexes = hexes_in_range(center, n=1)
        expected = {
            HexCoord(q=0, r=0),
            HexCoord(q=1, r=0),
            HexCoord(q=1, r=-1),
            HexCoord(q=0, r=-1),
            HexCoord(q=-1, r=0),
            HexCoord(q=-1, r=1),
            HexCoord(q=0, r=1),
        }
        assert set(hexes) == expected

    def test_range_two(self) -> None:
        """Test range 2 returns correct number of hexes."""
        center = HexCoord(q=0, r=0)
        hexes = hexes_in_range(center, n=2)
        # Formula: 3n^2 + 3n + 1 = 3(4) + 3(2) + 1 = 12 + 6 + 1 = 19
        assert len(hexes) == 19

    def test_range_three(self) -> None:
        """Test range 3 for scouting scenarios."""
        center = HexCoord(q=0, r=0)
        hexes = hexes_in_range(center, n=3)
        # Formula: 3(9) + 3(3) + 1 = 27 + 9 + 1 = 37
        assert len(hexes) == 37

    def test_range_formula(self) -> None:
        """Test the hex count formula: 3n^2 + 3n + 1."""
        center = HexCoord(q=0, r=0)
        for n in range(6):
            hexes = hexes_in_range(center, n=n)
            expected_count = 3 * n * n + 3 * n + 1
            assert len(hexes) == expected_count

    def test_range_all_within_distance(self) -> None:
        """Test that all returned hexes are within the specified distance."""
        center = HexCoord(q=2, r=-1)
        n = 3
        hexes = hexes_in_range(center, n=n)
        for hex_coord in hexes:
            assert hex_distance(center, hex_coord) <= n

    def test_range_no_duplicates(self) -> None:
        """Test that there are no duplicate hexes in range."""
        center = HexCoord(q=5, r=5)
        hexes = hexes_in_range(center, n=2)
        assert len(hexes) == len(set(hexes))

    def test_range_negative_center(self) -> None:
        """Test range query with negative center coordinates."""
        center = HexCoord(q=-3, r=-2)
        hexes = hexes_in_range(center, n=2)
        assert len(hexes) == 19
        assert center in hexes

    def test_range_large_value(self) -> None:
        """Test range with larger value (e.g., for foraging)."""
        center = HexCoord(q=0, r=0)
        hexes = hexes_in_range(center, n=5)
        # 3(25) + 3(5) + 1 = 75 + 15 + 1 = 91
        assert len(hexes) == 91

    def test_range_contains_neighbors(self) -> None:
        """Test that range >= 1 contains all neighbors."""
        center = HexCoord(q=1, r=1)
        hexes = hexes_in_range(center, n=1)
        neighbors = hex_neighbors(center)
        for neighbor in neighbors:
            assert neighbor in hexes


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_negative_range_raises_error(self) -> None:
        """Test that negative range raises ValueError."""
        center = HexCoord(q=0, r=0)
        with pytest.raises(ValueError, match="Range n must be non-negative"):
            hexes_in_range(center, n=-1)

    def test_very_large_coordinates(self) -> None:
        """Test system works with very large coordinates."""
        hex_a = HexCoord(q=10000, r=5000)
        hex_b = HexCoord(q=10001, r=5000)
        assert hex_distance(hex_a, hex_b) == 1

    def test_distance_zero_coords(self) -> None:
        """Test distance from origin to various zero-component coords."""
        origin = HexCoord(q=0, r=0)
        test_cases = [
            # (0,0) to (5,0): cube (0,0,0) to (5,-5,0) -> max(5,5,0) = 5
            (HexCoord(q=5, r=0), 5),
            # (0,0) to (0,5): cube (0,0,0) to (0,-5,5) -> max(0,5,5) = 5
            (HexCoord(q=0, r=5), 5),
            # (0,0) to (5,-5): cube (0,0,0) to (5,0,-5) -> max(5,0,5) = 5
            (HexCoord(q=5, r=-5), 5),
        ]
        for coord, expected in test_cases:
            assert hex_distance(origin, coord) == expected
