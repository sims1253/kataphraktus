"""Unit tests for movement domain logic."""

from unittest.mock import Mock

import pytest

from cataphract.domain.movement import (
    MovementType,
    calculate_daily_movement_miles,
    calculate_fording_delay,
    validate_movement_order,
)
from cataphract.models.army import Army, Detachment, UnitType
from cataphract.models.commander import Trait


class TestDomainMovement:
    """Test cases for movement domain logic."""

    def test_calculate_daily_movement_miles_standard_road(self):
        """Test standard movement on road."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 12.0  # Standard road speed

    def test_calculate_daily_movement_miles_standard_offroad(self):
        """Test standard movement off-road."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=False, traits=None, weather_modifier=0
        )

        assert miles == 6.0  # Standard off-road speed

    def test_calculate_daily_movement_miles_forced_march(self):
        """Test forced march speed."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.FORCED, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 18.0  # Forced march road speed

    def test_calculate_daily_movement_miles_cavalry_only_forced(self):
        """Test cavalry-only army doubles forced march speed."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "cavalry"
        det.unit_type.special_abilities = None
        det.soldier_count = 500
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 0

        miles = calculate_daily_movement_miles(
            army, MovementType.FORCED, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 36.0  # Cavalry-only doubles to 36

    def test_calculate_daily_movement_miles_mixed_not_cavalry_only(self):
        """Test mixed army does not get cavalry-only bonus."""
        army = Mock(spec=Army)
        det1 = Mock(spec=Detachment)
        det1.unit_type = Mock(spec=UnitType)
        det1.unit_type.category = "cavalry"
        det1.unit_type.special_abilities = None
        det1.soldier_count = 500
        det1.wagon_count = 0
        det2 = Mock(spec=Detachment)
        det2.unit_type = Mock(spec=UnitType)
        det2.unit_type.category = "infantry"
        det2.unit_type.special_abilities = None
        det2.soldier_count = 100
        det2.wagon_count = 0
        army.detachments = [det1, det2]
        army.noncombatant_count = 0

        miles = calculate_daily_movement_miles(
            army, MovementType.FORCED, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 18.0  # No cavalry-only bonus

    def test_calculate_daily_movement_miles_weather_penalty(self):
        """Test weather modifier reduces speed."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=True, traits=None, weather_modifier=-2
        )

        assert miles == 10.0  # 12 - 2 = 10

    def test_calculate_daily_movement_miles_ranger_ignores_weather(self):
        """Test Ranger trait ignores weather penalties."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        ranger_trait = Mock(spec=Trait)
        ranger_trait.name = "Ranger"

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=True, traits=[ranger_trait], weather_modifier=-2
        )

        assert miles == 12.0  # Weather ignored

    def test_calculate_daily_movement_miles_night_march(self):
        """Test night march speed."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.NIGHT, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 6.0  # Night march speed

    def test_calculate_daily_movement_miles_night_offroad_impossible(self):
        """Test night march off-road is impossible."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.NIGHT, on_road=False, traits=None, weather_modifier=0
        )

        assert miles == 0.0  # Cannot night march off-road

    def test_calculate_daily_movement_miles_column_length_cap_standard(self):
        """Test column length > 6 miles caps standard march at 6 miles."""
        army = Mock(spec=Army)
        # Create army with >6 mile column (30,000 infantry = 6 miles exactly, so 35,000 > 6)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.soldier_count = 35000
        det.wagon_count = 0
        det.unit_type.special_abilities = None
        army.detachments = [det]
        army.noncombatant_count = 0

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 6.0  # Capped at 6 for standard

    def test_calculate_daily_movement_miles_column_length_cap_forced(self):
        """Test column length > 6 miles caps forced march at 12 miles."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.soldier_count = 35000
        det.wagon_count = 0
        det.unit_type.special_abilities = None
        army.detachments = [det]
        army.noncombatant_count = 0

        miles = calculate_daily_movement_miles(
            army, MovementType.FORCED, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 12.0  # Capped at 12 for forced

    def test_calculate_daily_movement_miles_short_column_no_cap(self):
        """Test short column does not apply cap."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.soldier_count = 1000  # Small column
        det.wagon_count = 0
        det.unit_type.special_abilities = None
        army.detachments = [det]
        army.noncombatant_count = 0

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=True, traits=None, weather_modifier=0
        )

        assert miles == 12.0  # No cap, normal speed

    def test_calculate_daily_movement_miles_weather_cannot_go_negative(self):
        """Test extreme weather cannot result in negative movement."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        det.unit_type.special_abilities = None
        det.soldier_count = 1000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 250

        miles = calculate_daily_movement_miles(
            army, MovementType.STANDARD, on_road=False, traits=None, weather_modifier=-10
        )

        assert miles == 0.0  # Cannot go below 0

    def test_calculate_fording_delay_infantry_only(self):
        """Test fording delay for infantry army."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.unit_type.special_abilities = None
        det.soldier_count = 5000  # 1 mile column
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 0

        delay = calculate_fording_delay(army, traits=None)

        assert delay == 0.5  # 1 mile * 0.5 days/mile

    def test_calculate_fording_delay_cavalry_only(self):
        """Test fording delay for cavalry-only army (no delay)."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="cavalry")
        det.unit_type.special_abilities = None
        det.soldier_count = 2000
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 0

        delay = calculate_fording_delay(army, traits=None)

        assert delay == 0.0  # Cavalry fords at normal speed

    def test_calculate_fording_delay_with_noncombatants(self):
        """Test fording delay includes noncombatants in calculation."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.unit_type.special_abilities = None
        det.soldier_count = 2500
        det.wagon_count = 0
        army.detachments = [det]
        army.noncombatant_count = 2500  # Total 5000 = 1 mile

        delay = calculate_fording_delay(army, traits=None)

        assert delay == 0.5  # 1 mile * 0.5

    def test_calculate_fording_delay_with_wagons_raises_error(self):
        """Test fording with wagons raises ValueError."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.unit_type = Mock(spec=UnitType, category="infantry")
        det.unit_type.special_abilities = None
        det.soldier_count = 5000
        det.wagon_count = 5  # Has wagons
        army.detachments = [det]
        army.noncombatant_count = 0

        with pytest.raises(ValueError, match="cannot ford rivers"):
            calculate_fording_delay(army, traits=None)

    def test_calculate_fording_delay_mixed_army(self):
        """Test fording delay for mixed cavalry and infantry."""
        army = Mock(spec=Army)
        det1 = Mock(spec=Detachment)
        det1.unit_type = Mock(spec=UnitType, category="infantry")
        det1.unit_type.special_abilities = None
        det1.soldier_count = 5000
        det1.wagon_count = 0
        det2 = Mock(spec=Detachment)
        det2.unit_type = Mock(spec=UnitType, category="cavalry")
        det2.unit_type.special_abilities = None
        det2.soldier_count = 2000
        det2.wagon_count = 0
        army.detachments = [det1, det2]
        army.noncombatant_count = 0

        delay = calculate_fording_delay(army, traits=None)

        assert delay == 0.5  # Only infantry counts (1 mile * 0.5)

    def test_validate_movement_order_valid(self):
        """Test valid movement order."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 0
        army.detachments = [det]

        valid, error = validate_movement_order(
            army, off_road_legs=[False], has_river_fords=[False], is_night=False, traits=None
        )

        assert valid is True
        assert error is None

    def test_validate_movement_order_wagons_offroad_invalid(self):
        """Test wagons cannot go off-road."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army.detachments = [det]

        valid, error = validate_movement_order(
            army, off_road_legs=[True], has_river_fords=[False], is_night=False, traits=None
        )

        assert valid is False
        assert error is not None
        assert "off-road with wagons" in error.lower()

    def test_validate_movement_order_night_offroad_invalid(self):
        """Test cannot night march off-road."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 0
        army.detachments = [det]

        valid, error = validate_movement_order(
            army, off_road_legs=[True], has_river_fords=[False], is_night=True, traits=None
        )

        assert valid is False
        assert error is not None
        assert "night march off-road" in error.lower()

    def test_validate_movement_order_wagons_ford_invalid(self):
        """Test wagons cannot ford rivers."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army.detachments = [det]

        valid, error = validate_movement_order(
            army, off_road_legs=[False], has_river_fords=[True], is_night=False, traits=None
        )

        assert valid is False
        assert error is not None
        assert "ford rivers with wagons" in error.lower()

    def test_validate_movement_order_multiple_legs(self):
        """Test validation with multiple movement legs."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 0
        army.detachments = [det]

        valid, error = validate_movement_order(
            army,
            off_road_legs=[False, False, False],
            has_river_fords=[False, False, False],
            is_night=False,
            traits=None,
        )

        assert valid is True
        assert error is None

    def test_validate_movement_order_any_offroad_leg_with_wagons(self):
        """Test any off-road leg with wagons is invalid."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army.detachments = [det]

        valid, error = validate_movement_order(
            army,
            off_road_legs=[False, True, False],  # One off-road leg
            has_river_fords=[False, False, False],
            is_night=False,
            traits=None,
        )

        assert valid is False
        assert error is not None
        assert "off-road with wagons" in error.lower()

    def test_movement_type_enum_values(self):
        """Test MovementType enum has correct values."""
        assert MovementType.STANDARD.value == "standard"
        assert MovementType.FORCED.value == "forced"
        assert MovementType.NIGHT.value == "night"
