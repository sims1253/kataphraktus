"""Unit tests for MovementService."""

from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from cataphract.models import Army, Detachment, Hex, UnitType
from cataphract.services.movement_service import MovementService


class TestMovementService:
    """Test cases for MovementService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.movement_service = MovementService(self.mock_session)

    def test_calculate_movement_cost_road(self):
        """Test movement cost calculation on roads."""
        from_hex = Mock(spec=Hex)
        from_hex.q = 0
        from_hex.r = 0
        from_hex.has_road = True

        to_hex = Mock(spec=Hex)
        to_hex.q = 1
        to_hex.r = 0
        to_hex.has_road = True

        army = Mock(spec=Army)

        result = self.movement_service.calculate_movement_cost(from_hex, to_hex, army, is_road=True)

        # Distance should be 1 hex = 6 miles
        assert result == 6.0

    def test_calculate_movement_cost_offroad(self):
        """Test movement cost calculation off roads."""
        from_hex = Mock(spec=Hex)
        from_hex.q = 0
        from_hex.r = 0
        from_hex.has_road = False

        to_hex = Mock(spec=Hex)
        to_hex.q = 1
        to_hex.r = 0
        to_hex.has_road = False

        army = Mock(spec=Army)
        army.detachments = []

        result = self.movement_service.calculate_movement_cost(
            from_hex, to_hex, army, is_road=False
        )

        # Distance should be 1 hex * 6 miles * 2 (off-road penalty) = 12.0
        assert result == 12.0

    def test_calculate_movement_cost_with_wagons_offroad(self):
        """Test that armies with wagons cannot move off-road."""
        from_hex = Mock(spec=Hex)
        from_hex.q = 0
        from_hex.r = 0
        from_hex.has_road = False

        to_hex = Mock(spec=Hex)
        to_hex.q = 1
        to_hex.r = 0
        to_hex.has_road = False

        # Create army with wagons
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army.detachments = [det]

        result = self.movement_service.calculate_movement_cost(
            from_hex, to_hex, army, is_road=False
        )

        # Should return infinity since wagons can't go off-road
        assert result == float("inf")

    def test_can_move_offroad_with_only_infantry(self):
        """Test that armies without wagons can move off-road."""
        unit_type = Mock(spec=UnitType)
        unit_type.can_travel_offroad = True
        unit_type.special_abilities = {}

        det = Mock(spec=Detachment)
        det.unit_type = unit_type
        det.wagon_count = 0

        army = Mock(spec=Army)
        army.detachments = [det]

        result = self.movement_service.can_move_offroad(army)
        assert result

    def test_can_move_offroad_with_wagons(self):
        """Test that armies with wagons cannot move off-road."""
        unit_type = Mock(spec=UnitType)
        unit_type.can_travel_offroad = True
        unit_type.special_abilities = {}

        det = Mock(spec=Detachment)
        det.unit_type = unit_type
        det.wagon_count = 5  # Has wagons

        army = Mock(spec=Army)
        army.detachments = [det]

        result = self.movement_service.can_move_offroad(army)
        assert not result

    def test_can_move_offroad_with_non_offroad_units(self):
        """Test that armies with non-offroad units cannot move off-road."""
        unit_type = Mock(spec=UnitType)
        unit_type.can_travel_offroad = False
        unit_type.special_abilities = {}

        det = Mock(spec=Detachment)
        det.unit_type = unit_type
        det.wagon_count = 0

        army = Mock(spec=Army)
        army.detachments = [det]

        result = self.movement_service.can_move_offroad(army)
        assert not result

    def test_calculate_fording_time(self):
        """Test calculation of river fording time."""
        # Create an army with 10,000 infantry equivalent
        inf_det = Mock(spec=Detachment)
        inf_unit = Mock(spec=UnitType)
        inf_unit.category = "infantry"
        inf_det.unit_type = inf_unit
        inf_det.soldier_count = 10000

        # Cavalry doesn't affect fording time
        cav_det = Mock(spec=Detachment)
        cav_unit = Mock(spec=UnitType)
        cav_unit.category = "cavalry"
        cav_det.unit_type = cav_unit
        cav_det.soldier_count = 1000  # Cavalry doesn't add to fording time

        army = Mock(spec=Army)
        army.detachments = [inf_det, cav_det]
        army.noncombatant_count = 2500  # 25% of 10000 infantry

        result = self.movement_service.calculate_fording_time(army)

        # 10000 infantry + 2500 noncombatants = 12500 people
        # 12500 / 5000 = 2.5 miles of column
        # 2.5 * 0.5 = 1.25 days to ford
        assert result == 1.25

    def test_can_ford_with_wagons_no_wagons(self):
        """Test that armies without wagons can ford."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 0
        army.detachments = [det]

        result = self.movement_service.can_ford_with_wagons(army)
        assert result

    def test_can_ford_with_wagons_has_wagons(self):
        """Test that armies with wagons cannot ford."""
        army = Mock(spec=Army)
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army.detachments = [det]

        result = self.movement_service.can_ford_with_wagons(army)
        assert not result

    def test_calculate_movement_speed_normal_road(self):
        """Test normal movement speed on roads."""
        army = Mock(spec=Army)
        army.detachments = []
        army.noncombatant_count = 0

        result = self.movement_service.calculate_movement_speed(
            army, is_road=True, is_forced_march=False, is_night_march=False
        )

        assert result == 12.0  # Normal road speed: 12 miles/day

    def test_calculate_movement_speed_forced_road(self):
        """Test forced march movement speed on roads."""
        army = Mock(spec=Army)
        army.detachments = []
        army.noncombatant_count = 0

        result = self.movement_service.calculate_movement_speed(
            army, is_road=True, is_forced_march=True, is_night_march=False
        )

        assert result == 18.0  # Forced road speed: 18 miles/day

    def test_calculate_movement_speed_night_march(self):
        """Test night march movement speed."""
        army = Mock(spec=Army)

        result = self.movement_service.calculate_movement_speed(
            army, is_road=True, is_forced_march=False, is_night_march=True
        )

        assert result == 6.0  # Night march: 6 miles/night

    def test_calculate_movement_speed_forced_night_march(self):
        """Test forced night march movement speed."""
        army = Mock(spec=Army)

        result = self.movement_service.calculate_movement_speed(
            army, is_road=True, is_forced_march=True, is_night_march=True
        )

        assert result == 12.0  # Forced night march: 12 miles/night

    def test_calculate_movement_speed_cavalry_only_forced(self):
        """Test cavalry-only army gets double speed on forced march."""
        # Create cavalry-only army
        cav_det = Mock(spec=Detachment)
        cav_unit = Mock(spec=UnitType)
        cav_unit.category = "cavalry"
        cav_det.unit_type = cav_unit
        cav_det.soldier_count = 1000
        cav_det.wagon_count = 0

        army = Mock(spec=Army)
        army.detachments = [cav_det]
        army.noncombatant_count = 0

        result = self.movement_service.calculate_movement_speed(
            army, is_road=True, is_forced_march=True, is_night_march=False
        )

        # Normal forced march road speed is 18, cavalry only doubles it to 36
        assert result == 36.0

    def test_calculate_army_column_length(self):
        """Test army column length calculation."""
        # Create an army with 10,000 infantry, 2,000 cavalry, 50 wagons
        inf_det = Mock(spec=Detachment)
        inf_unit = Mock(spec=UnitType)
        inf_unit.category = "infantry"
        inf_det.unit_type = inf_unit
        inf_det.soldier_count = 10000
        inf_det.wagon_count = 0

        cav_det = Mock(spec=Detachment)
        cav_unit = Mock(spec=UnitType)
        cav_unit.category = "cavalry"
        cav_det.unit_type = cav_unit
        cav_det.soldier_count = 2000
        cav_det.wagon_count = 0

        army = Mock(spec=Army)
        army.detachments = [inf_det, cav_det]
        army.noncombatant_count = 2500  # 25% of 10000 infantry

        result = self.movement_service.calculate_army_column_length(army)

        # Infantry+NC: 10000 + 2500 = 12500 / 5000 = 2.5 miles
        # Cavalry: 2000 / 2000 = 1.0 mile
        # Wagons: 0 / 50 = 0 miles
        # Army column length is the MAXIMUM of these components (rules compliance)
        assert result == 2.5

    def test_calculate_movement_speed_long_army(self):
        """Test that long armies move at reduced speed."""
        # Create a mock long army by patching calculate_army_column_length
        army = Mock(spec=Army)

        with patch.object(self.movement_service, "calculate_army_column_length", return_value=8.0):
            # Non-forced march long army
            result = self.movement_service.calculate_movement_speed(
                army, is_road=True, is_forced_march=False, is_night_march=False
            )
            assert result == 6.0  # Long armies move at 6 miles/day

            # Forced march long army
            result = self.movement_service.calculate_movement_speed(
                army, is_road=True, is_forced_march=True, is_night_march=False
            )
            assert result == 12.0  # Long armies forced march at 12 miles/day

    def test_check_movement_constraints_valid(self):
        """Test movement constraints check with valid conditions."""
        army = Mock(spec=Army)
        army.detachments = []
        army.days_marched_this_week = 0

        destination_hex = Mock(spec=Hex)
        destination_hex.has_road = True
        destination_hex.id = 100

        self.mock_session.get.return_value = destination_hex

        result = self.movement_service.check_movement_constraints(army, 100)

        assert result["can_move"]
        assert len(result["errors"]) == 0

    def test_check_movement_constraints_no_road_with_wagons(self):
        """Test movement constraints with wagons trying to go off-road."""
        # Army with wagons
        det = Mock(spec=Detachment)
        det.wagon_count = 5
        army = Mock(spec=Army)
        army.detachments = [det]
        army.days_marched_this_week = 0

        # Destination is off-road
        destination_hex = Mock(spec=Hex)
        destination_hex.has_road = False
        destination_hex.id = 100

        self.mock_session.get.return_value = destination_hex

        result = self.movement_service.check_movement_constraints(army, 100)

        assert not result["can_move"]
        assert len(result["errors"]) > 0
        assert any("off-road" in error.lower() for error in result["errors"])

    def test_check_movement_constraints_night_march_off_road(self):
        """Test that night marches cannot go off-road."""
        army = Mock(spec=Army)
        army.detachments = []
        army.days_marched_this_week = 0

        # Destination is off-road
        destination_hex = Mock(spec=Hex)
        destination_hex.has_road = False
        destination_hex.id = 100

        self.mock_session.get.return_value = destination_hex

        result = self.movement_service.check_movement_constraints(army, 100, is_night_march=True)

        assert not result["can_move"]
        assert len(result["errors"]) > 0
        assert any(
            "night" in error.lower() and "off-road" in error.lower() for error in result["errors"]
        )

    def test_calculate_army_column_length_infantry_only(self):
        """Test column length calculation for infantry-only army.

        This verifies the CORRECT implementation using max() not sum().
        Column length should be the LONGEST component, not the sum.
        """
        army = Mock(spec=Army)
        army.noncombatant_count = 0

        # 10,000 infantry = 2 miles column
        det = Mock(spec=Detachment)
        det.soldier_count = 10000
        det.wagon_count = 0
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        army.detachments = [det]

        result = self.movement_service.calculate_army_column_length(army)

        assert result == 2.0  # 10,000 / 5,000 = 2 miles

    def test_calculate_army_column_length_cavalry_only(self):
        """Test column length calculation for cavalry-only army."""
        army = Mock(spec=Army)
        army.noncombatant_count = 0

        # 4,000 cavalry = 2 miles column
        det = Mock(spec=Detachment)
        det.soldier_count = 4000
        det.wagon_count = 0
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "cavalry"
        army.detachments = [det]

        result = self.movement_service.calculate_army_column_length(army)

        assert result == 2.0  # 4,000 / 2,000 = 2 miles

    def test_calculate_army_column_length_wagons_only(self):
        """Test column length calculation for wagon train."""
        army = Mock(spec=Army)
        army.noncombatant_count = 0

        # 100 wagons = 2 miles column
        det = Mock(spec=Detachment)
        det.soldier_count = 0
        det.wagon_count = 100
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        army.detachments = [det]

        result = self.movement_service.calculate_army_column_length(army)

        assert result == 2.0  # 100 / 50 = 2 miles

    def test_calculate_army_column_length_uses_max_not_sum(self):
        """CRITICAL TEST: Verify column length uses MAX of components, not SUM.

        This is the key rule from CATAPHRACT Ruleset.md:
        'marching armies stretch 1 mile of road per 5,000 infantry and noncombatants,
        2,000 cavalry, OR 50 wagons'

        The word 'OR' means we take the LONGEST component, not add them together.
        """
        army = Mock(spec=Army)
        army.noncombatant_count = 1000

        # Create army with:
        # - 4,000 infantry + 1,000 NC = 5,000 total = 1 mile
        # - 4,000 cavalry = 2 miles
        # - 50 wagons = 1 mile
        # Column length should be MAX(1, 2, 1) = 2 miles, NOT sum = 4 miles

        det1 = Mock(spec=Detachment)
        det1.soldier_count = 4000
        det1.wagon_count = 0
        det1.unit_type = Mock(spec=UnitType)
        det1.unit_type.category = "infantry"

        det2 = Mock(spec=Detachment)
        det2.soldier_count = 4000
        det2.wagon_count = 0
        det2.unit_type = Mock(spec=UnitType)
        det2.unit_type.category = "cavalry"

        det3 = Mock(spec=Detachment)
        det3.soldier_count = 0
        det3.wagon_count = 50
        det3.unit_type = Mock(spec=UnitType)
        det3.unit_type.category = "infantry"

        army.detachments = [det1, det2, det3]

        result = self.movement_service.calculate_army_column_length(army)

        # Should be 2.0 (from cavalry), NOT 4.0 (which would be sum)
        assert result == 2.0, f"Expected max(1, 2, 1) = 2.0, got {result}"

    def test_calculate_army_column_length_with_noncombatants(self):
        """Test that noncombatants are included in infantry column calculation."""
        army = Mock(spec=Army)
        army.noncombatant_count = 2500  # 2,500 NC

        # 2,500 infantry + 2,500 NC = 5,000 total = 1 mile
        det = Mock(spec=Detachment)
        det.soldier_count = 2500
        det.wagon_count = 0
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        army.detachments = [det]

        result = self.movement_service.calculate_army_column_length(army)

        assert result == 1.0  # (2,500 + 2,500) / 5,000 = 1.0

    def test_calculate_army_column_length_large_army(self):
        """Test column length for a large mixed army."""
        army = Mock(spec=Army)
        army.noncombatant_count = 5000

        # 20,000 infantry + 5,000 NC = 25,000 = 5 miles
        # 10,000 cavalry = 5 miles
        # 200 wagons = 4 miles
        # Max should be 5 miles

        det1 = Mock(spec=Detachment)
        det1.soldier_count = 20000
        det1.wagon_count = 0
        det1.unit_type = Mock(spec=UnitType)
        det1.unit_type.category = "infantry"

        det2 = Mock(spec=Detachment)
        det2.soldier_count = 10000
        det2.wagon_count = 0
        det2.unit_type = Mock(spec=UnitType)
        det2.unit_type.category = "cavalry"

        det3 = Mock(spec=Detachment)
        det3.soldier_count = 0
        det3.wagon_count = 200
        det3.unit_type = Mock(spec=UnitType)
        det3.unit_type.category = "infantry"

        army.detachments = [det1, det2, det3]

        result = self.movement_service.calculate_army_column_length(army)

        # Infantry: 25,000/5,000 = 5
        # Cavalry: 10,000/2,000 = 5
        # Wagons: 200/50 = 4
        # Max = 5
        assert result == 5.0

    def test_calculate_army_column_length_small_army(self):
        """Test column length for small army (less than 1 mile)."""
        army = Mock(spec=Army)
        army.noncombatant_count = 100

        # 500 infantry + 100 NC = 600 = 0.12 miles
        det = Mock(spec=Detachment)
        det.soldier_count = 500
        det.wagon_count = 0
        det.unit_type = Mock(spec=UnitType)
        det.unit_type.category = "infantry"
        army.detachments = [det]

        result = self.movement_service.calculate_army_column_length(army)

        # Should be 600 / 5000 = 0.12
        assert result == 0.12
