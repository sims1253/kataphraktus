"""Unit tests for HarryingService."""

from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from cataphract.models import Army, Commander, Detachment, UnitType
from cataphract.services.harrying_service import HarryingService


class FakeVisibilityService:
    """Fake implementation of IVisibilityService for testing."""

    def __init__(self):
        self.visible_armies = []

    def get_visible_armies(self, _commander, **_kwargs):
        return self.visible_armies

    def calculate_scouting_radius(self, _commander, **_kwargs):
        return 2


class TestHarryingService:
    """Test cases for HarryingService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.visibility = FakeVisibilityService()
        self.harrying_service = HarryingService(self.mock_session, self.visibility)

    def _create_mock_army_with_game(self, army_id=1, day=10):
        """Helper to create a mock army with properly configured game attributes."""
        army = Mock(spec=Army)
        army.id = army_id
        army.game = Mock()
        army.game.current_day = day
        army.game.current_day_part = "morning"
        army.commander = Mock(spec=Commander)
        return army

    def test_can_harry_army_garrisoned(self):
        """Test that garrisoned armies cannot be harried."""
        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.army = Mock(spec=Army)
        harrying_detachment.army.commander = Mock(spec=Commander)

        target_army = Mock(spec=Army)
        target_army.status = "garrisoned"  # Garrisoned armies cannot be harried

        # Set up fake visibility to say the army is visible
        self.visibility.visible_armies = [target_army]

        result = self.harrying_service.can_harry_army(harrying_detachment, target_army)
        assert not result  # Garrisoned army cannot be harried

    def test_can_harry_army_not_visible(self):
        """Test that armies outside scouting range cannot be harried."""
        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.army = Mock(spec=Army)
        harrying_detachment.army.commander = Mock(spec=Commander)

        target_army = Mock(spec=Army)
        target_army.status = "idle"
        target_army.id = 999  # Different ID

        # Set up fake visibility to not include the target army
        self.visibility.visible_armies = []  # Empty list, meaning not visible

        result = self.harrying_service.can_harry_army(harrying_detachment, target_army)
        assert not result  # Not visible, so can't harry

    def test_can_harry_army_visible_and_valid(self):
        """Test that visible non-garrisoned armies can be harried."""
        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.army = Mock(spec=Army)
        harrying_detachment.army.commander = Mock(spec=Commander)

        target_army = Mock(spec=Army)
        target_army.status = "idle"
        target_army.id = 123

        # Set up fake visibility to include the target army
        self.visibility.visible_armies = [target_army]

        result = self.harrying_service.can_harry_army(harrying_detachment, target_army)
        assert result  # Visible and not garrisoned, so can harry

    def test_harry_army_kill_successful(self):
        """Test successful 'kill' harrying action."""
        # Set up harrying detachment (infantry to keep it simple)
        detachment_unit = Mock(spec=UnitType)
        detachment_unit.name = "infantry"
        detachment_unit.category = "infantry"
        detachment_unit.special_abilities = {}

        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.unit_type = detachment_unit
        harrying_detachment.soldier_count = 1000
        harrying_detachment.army = self._create_mock_army_with_game(1)

        # Set up target army
        target_army = self._create_mock_army_with_game(2)
        target_army.supplies_current = 2000  # Represents army size/resources
        target_army.status_effects = {}

        # Set up fake visibility to include the target army
        self.visibility.visible_armies = [target_army]

        # Mock dice roll to be successful (≤ 2 base + 0 bonus = 2)
        with patch("cataphract.services.harrying_service.roll_dice", return_value={"total": 1}):
            result = self.harrying_service.harry_army(harrying_detachment, target_army, "kill")

            assert result["success"]
            assert result["objective"] == "kill"
            # Kill: 20% of detachment size = 20% of 1000 = 200
            assert result["damage_dealt"] == 200

    def test_harry_army_torch_successful(self):
        """Test successful 'torch' harrying action."""
        # Set up harrying detachment (infantry)
        detachment_unit = Mock(spec=UnitType)
        detachment_unit.name = "infantry"
        detachment_unit.category = "infantry"
        detachment_unit.special_abilities = {}

        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.unit_type = detachment_unit
        harrying_detachment.soldier_count = 500
        harrying_detachment.army = self._create_mock_army_with_game(1)

        # Set up target army
        target_army = self._create_mock_army_with_game(2)
        target_army.supplies_current = 2000
        target_army.status_effects = {}

        # Set up fake visibility to include the target army
        self.visibility.visible_armies = [target_army]

        # Mock dice roll to be successful and to have 2d6=8
        with patch(
            "cataphract.services.harrying_service.roll_dice",
            side_effect=[
                {"total": 1},  # For success check - successful
                {"total": 8},  # For damage calculation - 2d6 roll
            ],
        ):
            result = self.harrying_service.harry_army(harrying_detachment, target_army, "torch")

            assert result["success"]
            assert result["objective"] == "torch"
            # Torch: (2d6 + bonus) * detachment_size
            # With infantry, bonus = 0, so (8 + 0) * 500 = 4000
            # But target only has 2000 supplies, so it should be limited to 2000
            # Actually, it would be reduced by 4000, which would make it 0
            assert result["damage_dealt"] == 4000  # (8+0) * 500

    def test_harry_army_steal_successful(self):
        """Test successful 'steal' harrying action."""
        # Set up harrying detachment (skirmisher for bonus)
        detachment_unit = Mock(spec=UnitType)
        detachment_unit.name = "skirmisher"
        detachment_unit.category = "infantry"
        detachment_unit.special_abilities = {"harrying_bonus": 1}

        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.unit_type = detachment_unit
        harrying_detachment.soldier_count = 300
        harrying_detachment.army = self._create_mock_army_with_game(1)
        harrying_detachment.army.supplies_current = 500
        harrying_detachment.army.supplies_capacity = 1000

        # Set up target army
        target_army = self._create_mock_army_with_game(2)
        target_army.supplies_current = 1000
        target_army.status_effects = {}

        # Set up fake visibility to include the target army
        self.visibility.visible_armies = [target_army]

        # Mock dice roll to be successful and to have 1d6=5
        with patch(
            "cataphract.services.harrying_service.roll_dice",
            side_effect=[
                {"total": 1},  # For success check - successful
                {"total": 5},  # For amount calculation - 1d6 roll
            ],
        ):
            result = self.harrying_service.harry_army(harrying_detachment, target_army, "steal")

            assert result["success"]
            assert result["objective"] == "steal"
            # Steal: (1d6 + bonus) * detachment_size = (5 + 1) * 300 = 1800
            # But target only has 1000, so can only steal 1000
            assert result["damage_dealt"] == 1000  # Capped by target's supplies

    def test_harry_army_failed(self):
        """Test failed harrying action (harrying detachment takes casualties)."""
        # Set up harrying detachment
        detachment_unit = Mock(spec=UnitType)
        detachment_unit.name = "infantry"
        detachment_unit.category = "infantry"
        detachment_unit.special_abilities = {}

        harrying_detachment = Mock(spec=Detachment)
        harrying_detachment.unit_type = detachment_unit
        harrying_detachment.soldier_count = 1000
        harrying_detachment.army = self._create_mock_army_with_game(1)

        # Set up target army
        target_army = self._create_mock_army_with_game(2)
        target_army.supplies_current = 1000
        target_army.status_effects = {}

        # Set up fake visibility to include the target army
        self.visibility.visible_armies = [target_army]

        # Mock dice roll to be failure (e.g., roll 4 with threshold 2)
        with patch("cataphract.services.harrying_service.roll_dice", return_value={"total": 4}):
            result = self.harrying_service.harry_army(harrying_detachment, target_army, "kill")

            assert not result["success"]
            assert result["losses"] == 200  # 20% of 1000 = 200 casualties

    def test_get_harrying_targets(self):
        """Test getting armies that can be harried."""
        harrying_army = Mock(spec=Army)
        harrying_army.commander = Mock(spec=Commander)

        detachment = Mock(spec=Detachment)
        detachment.army = harrying_army
        detachment.soldier_count = 500

        # Create target armies
        garrisoned_army = Mock(spec=Army)
        garrisoned_army.id = 999
        garrisoned_army.status = "garrisoned"

        idle_army = Mock(spec=Army)
        idle_army.id = 888
        idle_army.status = "idle"

        # Set up fake visibility to return both armies
        self.visibility.visible_armies = [garrisoned_army, idle_army]

        result = self.harrying_service.get_harrying_targets(detachment)

        # Should only return the idle army (not garrisoned)
        assert len(result) == 1
        assert result[0].id == 888
        assert result[0].status == "idle"

    def test_apply_harried_effects(self):
        """Test applying harried status effects to an army."""
        army = Mock(spec=Army)
        army.status_effects = {"harried": {"until_day": 10, "by_detachment_id": 5}}

        result = self.harrying_service.apply_harried_effects(army)

        assert result["effects_applied"] == ["half_speed", "cannot_rest"]
        assert result["speed_reduction"] == 0.5
        assert not result["can_rest"]

    def test_apply_harried_effects_not_harried(self):
        """Test applying harried status effects to a non-harried army."""
        army = Mock(spec=Army)
        army.status_effects = {}  # Not harried

        result = self.harrying_service.apply_harried_effects(army)

        assert result["effects_applied"] == []
        assert result["speed_reduction"] == 0
        assert result["can_rest"]
