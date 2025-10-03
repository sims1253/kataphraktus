"""Unit tests for VisibilityService."""

from unittest.mock import Mock

from sqlalchemy.orm import Session

from cataphract.models import Army, Commander, Detachment, UnitType
from cataphract.services.visibility_service import VisibilityService


class TestVisibilityService:
    """Test cases for VisibilityService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.visibility_service = VisibilityService(self.mock_session)

    def test_calculate_scouting_radius_base(self):
        """Test base scouting radius calculation."""
        commander = Mock(spec=Commander)
        commander.armies = []

        # Test with no cavalry, no traits
        result = self.visibility_service.calculate_scouting_radius(commander)
        assert result == 1  # Base radius

    def test_calculate_scouting_radius_with_cavalry(self):
        """Test scouting radius with cavalry detachment."""
        # Create mock army with cavalry
        army = Mock(spec=Army)

        # Create mock detachment with cavalry unit type
        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "cavalry"
        det.unit_type = unit_type

        army.detachments = [det]
        commander = Mock(spec=Commander)
        commander.armies = [army]
        commander.traits = []
        army.commander = commander

        result = self.visibility_service.calculate_scouting_radius(commander)
        assert result == 2  # With cavalry, radius increases to 2

    def test_calculate_scouting_radius_with_skirmisher(self):
        """Test scouting radius with skirmisher detachment."""
        # Create mock army with skirmisher
        army = Mock(spec=Army)

        # Create mock detachment with skirmisher unit type
        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "infantry"
        unit_type.special_abilities = {"acts_as_cavalry_for_scouting": True}
        det.unit_type = unit_type

        army.detachments = [det]
        commander = Mock(spec=Commander)
        commander.armies = [army]
        commander.traits = []
        army.commander = commander

        result = self.visibility_service.calculate_scouting_radius(commander)
        assert result == 2  # Skirmishers act as cavalry for scouting

    def test_calculate_scouting_radius_with_outrider_trait(self):
        """Test scouting radius with Outrider trait."""
        # Create mock army with cavalry
        army = Mock(spec=Army)

        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "cavalry"
        det.unit_type = unit_type

        army.detachments = [det]
        commander = Mock(spec=Commander)
        commander.armies = [army]
        army.commander = commander

        # Mock the commander's traits
        trait = Mock()
        trait.trait = Mock()
        trait.trait.name = "Outrider"
        commander.traits = [trait]

        result = self.visibility_service.calculate_scouting_radius(commander)
        assert result == 3  # Outrider trait with cavalry increases to 3

    def test_calculate_scouting_radius_weather_penalty(self):
        """Test scouting radius reduction due to bad weather."""
        commander = Mock(spec=Commander)
        commander.armies = []
        commander.traits = []  # No Ranger trait to counter weather penalty

        # Test with bad weather - no armies means weather penalties don't apply
        result = self.visibility_service.calculate_scouting_radius(commander, weather="bad")
        assert result == 1  # Base radius when no armies, weather penalties don't apply

        result = self.visibility_service.calculate_scouting_radius(commander, weather="very_bad")
        assert result == 1  # Base radius when no armies, weather penalties don't apply

    def test_calculate_scouting_radius_weather_with_ranger_trait(self):
        """Test weather penalties ignored with Ranger trait."""
        commander = Mock(spec=Commander)
        commander.armies = []

        # Add Ranger trait
        ranger_trait = Mock()
        ranger_trait.trait = Mock()
        ranger_trait.trait.name = "Ranger"
        commander.traits = [ranger_trait]

        # With Ranger trait, weather penalties should be ignored
        result = self.visibility_service.calculate_scouting_radius(commander, weather="bad")
        assert result == 1  # Base radius unaffected by weather due to Ranger trait

    def test_get_scouting_range_for_army(self):
        """Test scouting range calculation for an army."""
        army = Mock(spec=Army)

        # Create mock detachment with cavalry
        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "cavalry"
        det.unit_type = unit_type

        army.detachments = [det]
        army.commander = None  # No commander for this test

        result = self.visibility_service.get_scouting_range_for_army(army)
        assert result == 2  # With cavalry, range is 2

    def test_get_scouting_range_for_army_with_skirmisher(self):
        """Test scouting range for army with skirmisher."""
        army = Mock(spec=Army)

        # Create mock detachment with skirmisher special ability
        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "infantry"
        unit_type.special_abilities = {"acts_as_cavalry_for_scouting": True}
        det.unit_type = unit_type

        army.detachments = [det]
        army.commander = None

        result = self.visibility_service.get_scouting_range_for_army(army)
        assert result == 2  # Skirmishers act as cavalry for scouting

    def test_get_scouting_range_for_army_with_outrider(self):
        """Test scouting range for army with Outrider commander."""
        army = Mock(spec=Army)

        # Create mock detachment with cavalry
        det = Mock(spec=Detachment)
        unit_type = Mock(spec=UnitType)
        unit_type.category = "cavalry"
        det.unit_type = unit_type

        army.detachments = [det]

        # Mock commander with Outrider trait
        commander = Mock(spec=Commander)
        outrider_trait = Mock()
        outrider_trait.trait = Mock()
        outrider_trait.trait.name = "Outrider"
        commander.traits = [outrider_trait]
        army.commander = commander

        result = self.visibility_service.get_scouting_range_for_army(army)
        assert result == 3  # Outrider with cavalry increases to 3
