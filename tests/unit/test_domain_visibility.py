"""Unit tests for visibility domain helpers."""

from unittest.mock import Mock

from cataphract.domain.visibility import calculate_scouting_radius, get_visible_hexes
from cataphract.models.army import Army, Detachment, UnitType


def _make_skirmisher_detachment() -> Detachment:
    unit_type = Mock(spec=UnitType)
    unit_type.category = "infantry"
    unit_type.special_abilities = {"acts_as_cavalry_for_scouting": True}

    detachment = Mock(spec=Detachment)
    detachment.unit_type = unit_type
    detachment.soldier_count = 500
    return detachment


def test_calculate_scouting_radius_counts_skirmishers():
    """Skirmishers with scouting ability should extend the radius to two hexes."""
    army = Mock(spec=Army)
    army.detachments = [_make_skirmisher_detachment()]

    radius = calculate_scouting_radius(army, traits=None)

    assert radius == 2


def test_get_visible_hexes_returns_coordinate_tuples():
    """get_visible_hexes should return axial coordinate tuples, including center."""
    visible = get_visible_hexes(0, 0, radius=1)

    expected = {
        (0, 0),
        (1, 0),
        (1, -1),
        (0, -1),
        (-1, 0),
        (-1, 1),
        (0, 1),
    }

    assert visible == expected
