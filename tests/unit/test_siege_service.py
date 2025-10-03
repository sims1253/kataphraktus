"""Unit tests for SiegeService."""

from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from cataphract.models import Army, Siege, Stronghold
from cataphract.services.siege_service import SiegeService


class FakeBattleService:
    """Fake battle service for testing."""

    def __init__(self):
        self.battle_result = None  # Can be set in tests

    def resolve_battle(self, _attacker_armies, _defender_armies, _hex_id, **_kwargs):
        """Return test battle result."""
        return self.battle_result or {"victor": "attacker", "casualties": {}}


class FakeMoraleService:
    """Fake morale service for testing."""

    def __init__(self):
        self.morale_check_result = (True, "", 10)  # (success, consequence, roll)

    def check_morale(self, _army):
        """Return test morale check result."""
        return self.morale_check_result

    def apply_consequence(self, _army, _consequence):
        """Return test consequence result."""
        return {"applied": True}


class TestSiegeService:
    """Test cases for SiegeService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.battle = FakeBattleService()
        self.morale = FakeMoraleService()
        self.siege_service = SiegeService(self.mock_session, self.battle, self.morale)

    def test_start_siege_success(self):
        """Test successfully starting a siege."""
        # Create mock objects
        attacker_army = Mock(spec=Army)
        attacker_army.id = 100
        attacker_army.game_id = Mock()
        attacker_army.game_id.current_day = 50

        stronghold = Mock(spec=Stronghold)
        stronghold.id = 200
        stronghold.garrison = None  # No garrison
        stronghold.base_threshold = 15  # Fortress threshold

        # Mock query to return no existing siege
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        self.mock_session.query.return_value = mock_query

        # Configure mock to set siege.id when add() is called
        def set_siege_id(siege):
            siege.id = 1

        self.mock_session.add.side_effect = set_siege_id

        result = self.siege_service.start_siege(attacker_army, stronghold)

        assert result["success"]
        assert result["siege_id"] is not None
        assert result["message"].startswith("Siege of")

        # Verify that a Siege object was created and added to session
        assert self.mock_session.add.called
        assert self.mock_session.commit.called

    def test_start_siege_already_ongoing(self):
        """Test starting a siege when one is already ongoing."""
        # Create mock objects
        attacker_army = Mock(spec=Army)
        attacker_army.game_id = Mock()

        stronghold = Mock(spec=Stronghold)
        stronghold.id = 200

        # Mock an existing ongoing siege
        existing_siege = Mock(spec=Siege)
        existing_siege.status = "ongoing"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_siege
        self.mock_session.query.return_value = mock_query

        result = self.siege_service.start_siege(attacker_army, stronghold)

        assert not result["success"]
        assert "already under siege" in result["message"]

    def test_progress_siege_weekly_basic(self):
        """Test weekly siege progression with basic modifiers."""
        # Create a mock siege
        siege = Mock(spec=Siege)
        siege.current_threshold = 15
        siege.weeks_elapsed = 0
        siege.threshold_modifiers = {}
        siege.siege_engines_count = 0
        siege.status = "ongoing"
        siege.attacker_armies = []
        siege.game_id = 1
        siege.started_on_day = 50
        siege.stronghold_id = 100

        # Mock dice roll that doesn't exceed threshold (no gates opening)
        with patch("cataphract.services.siege_service.roll_dice", return_value={"total": 4}):
            result = self.siege_service.progress_siege_weekly(siege)

            # Should have applied -1 default modifier
            assert result["threshold_change"] == -1
            assert siege.current_threshold == 14  # 15 - 1 = 14
            assert siege.weeks_elapsed == 1
            assert not result["gates_opened"]

    def test_progress_siege_weekly_gates_open(self):
        """Test weekly siege progression resulting in gates opening."""
        # Create a mock siege with a low threshold
        siege = Mock(spec=Siege)
        siege.current_threshold = 5
        siege.weeks_elapsed = 0
        siege.threshold_modifiers = {}
        siege.siege_engines_count = 0
        siege.status = "ongoing"
        siege.attacker_armies = []
        siege.game_id = 1
        siege.started_on_day = 50
        siege.stronghold_id = 100

        # Mock dice roll that exceeds threshold (gates open)
        with patch("cataphract.services.siege_service.roll_dice", return_value={"total": 8}):
            result = self.siege_service.progress_siege_weekly(siege)

            assert result["gates_opened"]
            assert siege.status == "gates_opened"

    def test_progress_siege_weekly_with_siege_engines(self):
        """Test weekly siege progression with siege engines."""
        # Create a mock siege with siege engines
        siege = Mock(spec=Siege)
        siege.current_threshold = 15
        siege.weeks_elapsed = 0
        siege.threshold_modifiers = {}
        siege.siege_engines_count = 20  # 20 engines = -2 to threshold
        siege.status = "ongoing"
        siege.attacker_armies = []
        siege.game_id = 1
        siege.started_on_day = 50
        siege.stronghold_id = 100

        # Mock dice roll
        with patch("cataphract.services.siege_service.roll_dice", return_value={"total": 4}):
            result = self.siege_service.progress_siege_weekly(siege)

            # Should have applied -1 default + -2 from engines = -3 total
            assert result["threshold_change"] == -3
            assert siege.current_threshold == 12  # 15 - 3 = 12
            assert siege.weeks_elapsed == 1

    def test_get_siege_engines_build_time(self):
        """Test getting siege engines build time based on traits."""
        # Without Siege Engineer trait (default)
        build_time = self.siege_service.get_siege_engines_build_time(is_siege_engineer=False)
        assert build_time == 30  # 1 month in days

        # With Siege Engineer trait
        build_time = self.siege_service.get_siege_engines_build_time(is_siege_engineer=True)
        assert build_time == 7  # 1 week in days

    def test_build_siege_engines(self):
        """Test building siege engines."""
        army = Mock(spec=Army)

        # Test with Siege Engineer trait
        result = self.siege_service.build_siege_engines(army, 20, is_siege_engineer=True)

        assert result["success"]
        assert result["engines_built"] == 20
        # 20 engines = 2 groups of 10, each takes 7 days with Siege Engineer = 14 days total
        assert result["time_required_days"] == 14

        # Test with invalid count (not multiple of 10)
        result = self.siege_service.build_siege_engines(army, 15, is_siege_engineer=True)

        assert not result["success"]
        assert "groups of 10" in result["message"]

    def test_deconstruct_siege_engines(self):
        """Test deconstructing siege engines."""
        army = Mock(spec=Army)
        det = Mock()
        det.wagon_count = 50  # Army has wagons to load engines
        army.detachments = [det]

        # Test deconstructing valid number of engines
        result = self.siege_service.deconstruct_siege_engines(army, 10)

        # 10 engines need 20 wagons (10*2), and should take 7 days
        assert result["success"]
        assert result["engines_deconstructed"] == 10
        assert result["wagons_needed"] == 20
        assert result["time_required_days"] == 7

    def test_deconstruct_siege_engines_insufficient_wagons(self):
        """Test deconstructing siege engines with insufficient wagons."""
        army = Mock(spec=Army)
        det = Mock()
        det.wagon_count = 5  # Only 5 wagons, need 20 for 10 engines
        army.detachments = [det]

        result = self.siege_service.deconstruct_siege_engines(army, 10)

        assert not result["success"]
        assert "empty wagons" in result["message"]

    def test_deconstruct_siege_engines_invalid_count(self):
        """Test deconstructing siege engines with invalid count."""
        army = Mock(spec=Army)
        army.detachments = []

        result = self.siege_service.deconstruct_siege_engines(army, 15)  # Not multiple of 10

        assert not result["success"]
        assert "groups of 10" in result["message"]

    def test_capture_stronghold_pillage(self):
        """Test capturing a stronghold with pillage."""
        victor_army = Mock(spec=Army)
        victor_army.loot_carried = 500
        victor_army.supplies_current = 2000
        victor_army.supplies_capacity = 3000
        victor_army.morale_current = 8
        victor_army.morale_max = 12
        victor_army.noncombatant_count = 250
        victor_army.commander = Mock()
        victor_army.commander.faction_id = 1
        victor_army.game_id = 1
        victor_army.game = Mock()
        victor_army.game.current_day = 50
        victor_army.game.current_day_part = "morning"

        stronghold = Mock(spec=Stronghold)
        stronghold.id = 100
        stronghold.loot_held = 10000
        stronghold.supplies_held = 5000
        stronghold.controlling_faction_id = 1
        stronghold.type = "town"

        # Mock roll_dice to return a predictable value (0 supplies from dice roll)
        with patch("cataphract.services.siege_service.roll_dice", return_value={"total": 0}):
            result = self.siege_service.capture_stronghold(
                victor_army, stronghold, allow_pillage=True
            )

        assert result["success"]
        assert result["pillage_chosen"]
        assert result["loot_gained"] == 5000  # Half of 10000
        assert result["supplies_gained"] == 2500  # Half of 5000 (from pillage, 0 from dice)
        assert result["morale_change"] == 2  # +2 morale for pillaging

        # Verify army stats were updated
        assert victor_army.loot_carried >= 5000  # At least increased by pillage amount
        assert victor_army.morale_current >= 10  # Should be increased by 2 (up to max 12)

    def test_capture_stronghold_no_pillage(self):
        """Test capturing a stronghold without pillage."""
        victor_army = Mock(spec=Army)
        victor_army.loot_carried = 500
        victor_army.supplies_current = 2000
        victor_army.supplies_capacity = 3000
        victor_army.morale_current = 8
        victor_army.morale_max = 12
        victor_army.noncombatant_count = 250
        victor_army.commander = Mock()
        victor_army.commander.faction_id = 1
        victor_army.game_id = 1
        victor_army.game = Mock()
        victor_army.game.current_day = 50
        victor_army.game.current_day_part = "morning"

        stronghold = Mock(spec=Stronghold)
        stronghold.id = 100
        stronghold.loot_held = 10000
        stronghold.supplies_held = 5000
        stronghold.controlling_faction_id = 1
        stronghold.type = "city"

        # Set morale check to be successful (no morale issues)
        self.morale.morale_check_result = (True, "army_holds", 7)

        result = self.siege_service.capture_stronghold(victor_army, stronghold, allow_pillage=False)

        assert result["success"]
        assert not result["pillage_chosen"]
        # Army doesn't get the full resources but may get some based on other mechanics
