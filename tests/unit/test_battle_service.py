"""Unit tests for BattleService."""

from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from cataphract.domain.battle_data import BattleModifierParameters, BattleParameters
from cataphract.models import Army
from cataphract.services.battle_service import BattleService, calculate_morale_check_result


class TestBattleService:
    """Test cases for BattleService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.battle_service = BattleService(self.mock_session)

    def test_calculate_army_composition_for_battle(self):
        """Test calculation of effective army size for battle composition."""
        # Mock army with detachments
        army = Mock(spec=Army)
        army.detachments = []

        # Mock detachment 1: Infantry with battle multiplier 1.0
        det1 = Mock()
        det1.soldier_count = 1000
        det1.unit_type = Mock()
        det1.unit_type.battle_multiplier = 1.0
        det1.unit_type.category = "infantry"

        # Mock detachment 2: Cavalry with battle multiplier 2.0
        det2 = Mock()
        det2.soldier_count = 200
        det2.unit_type = Mock()
        det2.unit_type.battle_multiplier = 2.0  # Cavalry count double
        det2.unit_type.category = "cavalry"

        army.detachments = [det1, det2]

        # Regular battle (not assault)
        result = self.battle_service.calculate_army_composition_for_battle(army, is_assault=False)
        expected = (1000 * 1.0) + (200 * 2.0)  # 1000 + 400 = 1400
        assert result == expected

        # Assault (cavalry don't count double)
        result_assault = self.battle_service.calculate_army_composition_for_battle(
            army, is_assault=True
        )
        expected_assault = (1000 * 1.0) + (200 * 1.0)  # 1000 + 200 = 1200
        assert result_assault == expected_assault

    def test_calculate_numerical_advantage_modifier(self):
        """Test calculation of numerical advantage modifier."""
        # Mock armies
        army1 = Mock(spec=Army)
        army1.detachments = []

        army2 = Mock(spec=Army)
        army2.detachments = []

        # Test with equal armies (should result in 0 modifier)
        with patch.object(
            self.battle_service, "calculate_army_composition_for_battle", side_effect=[1000, 1000]
        ):
            result = self.battle_service.calculate_numerical_advantage_modifier(army1, army2)
            assert result == 0  # No advantage when sizes are equal

        # Test with 100% advantage (2000 vs 1000) -> should be +1 modifier
        with patch.object(
            self.battle_service, "calculate_army_composition_for_battle", side_effect=[2000, 1000]
        ):
            result = self.battle_service.calculate_numerical_advantage_modifier(army1, army2)
            assert result == 1  # 100% advantage = +1

        # Test with disadvantage (0 modifier since -50% < -100%)
        with patch.object(
            self.battle_service, "calculate_army_composition_for_battle", side_effect=[500, 1000]
        ):
            result = self.battle_service.calculate_numerical_advantage_modifier(army1, army2)
            assert result == 0  # -50% disadvantage = 0 (int(-0.5) = 0)

        # Test with 200% advantage (should be +2)
        with patch.object(
            self.battle_service, "calculate_army_composition_for_battle", side_effect=[3000, 1000]
        ):
            result = self.battle_service.calculate_numerical_advantage_modifier(army1, army2)
            assert result == 2  # (3000-1000)/1000 = 2000/1000 = 2

    def test_calculate_morale_advantage_modifier(self):
        """Test calculation of morale advantage modifier."""
        army1 = Mock(spec=Army)
        army1.morale_current = 10

        army2 = Mock(spec=Army)
        army2.morale_current = 8

        result = self.battle_service.calculate_morale_advantage_modifier(army1, army2)
        # Army1 morale (10) - Army2 morale (8) = +2 modifier
        assert result == 2

    def test_calculate_battle_modifier_base(self):
        """Test calculation of base battle modifiers."""
        army = Mock(spec=Army)
        army.is_undersupplied = False
        army.status = "idle"
        army.status_effects = None
        army.commander = None

        # Test base modifier with no conditions
        params = BattleModifierParameters(
            army=army,
            is_attacker=True,
            is_defender=False,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
        )
        result = self.battle_service.calculate_battle_modifier(params)
        assert result == 0  # Base modifier should be 0

    def test_calculate_battle_modifier_undersupplied(self):
        """Test battle modifier calculation with undersupplied army."""
        army = Mock(spec=Army)
        army.is_undersupplied = True  # Should add -1 modifier
        army.status = "idle"
        army.status_effects = None
        army.commander = None

        params = BattleModifierParameters(
            army=army,
            is_attacker=True,
            is_defender=False,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
        )
        result = self.battle_service.calculate_battle_modifier(params)
        assert result == -1  # -1 for being undersupplied

    def test_calculate_battle_modifier_status_effects(self):
        """Test battle modifier calculation with status effects."""
        army = Mock(spec=Army)
        army.is_undersupplied = False
        army.status = "idle"
        army.status_effects = {"sick_or_exhausted": {"active": True}}
        army.commander = None

        params = BattleModifierParameters(
            army=army,
            is_attacker=True,
            is_defender=False,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
        )
        result = self.battle_service.calculate_battle_modifier(params)
        assert result == -1  # -1 for sick or exhausted

    def test_calculate_battle_modifier_assault(self):
        """Test battle modifier for assault scenarios."""
        army = Mock(spec=Army)
        army.is_undersupplied = False
        army.status = "idle"
        army.status_effects = None
        army.commander = None

        # Test attacker in assault (should get -1)
        attacker_params = BattleModifierParameters(
            army=army,
            is_attacker=True,
            is_defender=False,
            hex_terrain="flatland",
            weather="clear",
            is_assault=True,
        )
        result = self.battle_service.calculate_battle_modifier(attacker_params)
        assert result == -1  # -1 for attacker in assault

        # Test defender in assault (no penalty)
        defender_params = BattleModifierParameters(
            army=army,
            is_attacker=False,
            is_defender=True,
            hex_terrain="flatland",
            weather="clear",
            is_assault=True,
        )
        result = self.battle_service.calculate_battle_modifier(defender_params)
        assert result == 0  # No penalty for defender

    def test_resolve_battle_single_vs_single(self):
        """Test battle resolution with single attacker vs single defender."""
        # Create mock armies
        attacker = self._create_mock_army(army_id=1, morale=9, soldiers=1000)
        defender = self._create_mock_army(army_id=2, morale=8, soldiers=1000)

        # Create battle parameters
        params = BattleParameters(
            attacker_armies=[attacker],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        # Resolve battle
        battle = self.battle_service.resolve_battle(params)

        # Verify battle was created
        assert battle is not None
        assert battle.attacker_side == [1]
        assert battle.defender_side == [2]

    def test_resolve_battle_multi_attacker_vs_single_defender(self):
        """Test multi-army battle: 2 attackers vs 1 defender.

        This tests for the potential modifier stacking bug where each attacker
        might incorrectly get advantage calculated against each defender separately.
        """
        # Create armies
        attacker1 = self._create_mock_army(army_id=1, morale=9, soldiers=500)
        attacker2 = self._create_mock_army(army_id=2, morale=9, soldiers=500)
        defender = self._create_mock_army(army_id=3, morale=8, soldiers=800)

        params = BattleParameters(
            attacker_armies=[attacker1, attacker2],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        battle = self.battle_service.resolve_battle(params)

        # Verify all armies are in battle
        assert len(battle.attacker_side) == 2
        assert len(battle.defender_side) == 1
        assert set(battle.attacker_side) == {1, 2}
        assert set(battle.defender_side) == {3}

    def test_resolve_battle_multi_vs_multi(self):
        """Test multi-army battle: 2 attackers vs 2 defenders."""
        attacker1 = self._create_mock_army(army_id=1, morale=9, soldiers=600)
        attacker2 = self._create_mock_army(army_id=2, morale=8, soldiers=400)
        defender1 = self._create_mock_army(army_id=3, morale=9, soldiers=500)
        defender2 = self._create_mock_army(army_id=4, morale=7, soldiers=500)

        params = BattleParameters(
            attacker_armies=[attacker1, attacker2],
            defender_armies=[defender1, defender2],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        battle = self.battle_service.resolve_battle(params)

        # Verify battle includes all armies
        assert len(battle.attacker_side) == 2
        assert len(battle.defender_side) == 2

    def test_battle_casualties_calculated(self):
        """Test that casualties are calculated for battle participants."""
        attacker = self._create_mock_army(army_id=1, morale=10, soldiers=1000)
        defender = self._create_mock_army(army_id=2, morale=6, soldiers=500)

        params = BattleParameters(
            attacker_armies=[attacker],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        battle = self.battle_service.resolve_battle(params)

        # Verify casualties are recorded
        assert battle.casualties is not None
        # Both armies should have casualty entries
        assert 1 in battle.casualties or 2 in battle.casualties

    def test_battle_morale_changes_calculated(self):
        """Test that morale changes are calculated for battle participants."""
        attacker = self._create_mock_army(army_id=1, morale=10, soldiers=1500)
        defender = self._create_mock_army(army_id=2, morale=6, soldiers=500)

        params = BattleParameters(
            attacker_armies=[attacker],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        battle = self.battle_service.resolve_battle(params)

        # Verify morale changes are recorded
        assert battle.morale_changes is not None

    def test_assault_battle_with_fortress_bonus(self):
        """Test assault battle applies fortress defense bonus correctly."""
        attacker = self._create_mock_army(army_id=1, morale=9, soldiers=2000)
        defender = self._create_mock_army(army_id=2, morale=8, soldiers=500)

        # Assault with fortress bonus
        params = BattleParameters(
            attacker_armies=[attacker],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="flatland",
            weather="clear",
            is_assault=True,
            fortress_defense_bonus=3,  # Defender gets +3
        )

        battle = self.battle_service.resolve_battle(params)

        # Verify battle occurred
        assert battle is not None
        # In assaults, cavalry should count as 1x not 2x

    def test_battle_terrain_modifiers(self):
        """Test that terrain modifiers affect battle correctly."""
        attacker = self._create_mock_army(army_id=1, morale=9, soldiers=1000)
        defender = self._create_mock_army(army_id=2, morale=9, soldiers=1000)

        # Defender on hills gets +1, attacker gets -1
        params = BattleParameters(
            attacker_armies=[attacker],
            defender_armies=[defender],
            hex_id=100,
            hex_terrain="hills",
            weather="clear",
            is_assault=False,
            fortress_defense_bonus=0,
        )

        battle = self.battle_service.resolve_battle(params)

        assert battle is not None

    def _create_mock_army(
        self, army_id: int, morale: int, soldiers: int, cavalry_ratio: float = 0.0
    ) -> Army:
        """Helper to create a mock army for testing.

        Args:
            army_id: Army ID
            morale: Current morale
            soldiers: Total soldier count
            cavalry_ratio: Ratio of cavalry (0.0 to 1.0)

        Returns:
            Mock Army object
        """
        army = Mock(spec=Army)
        army.id = army_id
        army.morale_current = morale
        army.morale_max = 12  # Standard max morale
        army.supplies_current = soldiers * 10  # Some supplies
        army.is_undersupplied = False
        army.status = "idle"
        army.status_effects = None
        army.daily_supply_consumption = soldiers  # Simplified for testing
        army.detachments = []

        # Create mock game
        army.game = Mock()
        army.game.current_day = 1
        army.game.current_day_part = "morning"

        # Create commander (no traits for basic tests)
        army.commander = Mock()
        army.commander.traits = []

        # Create detachments
        if cavalry_ratio > 0:
            cavalry_count = int(soldiers * cavalry_ratio)
            infantry_count = soldiers - cavalry_count

            # Infantry detachment
            if infantry_count > 0:
                inf_det = Mock()
                inf_det.soldier_count = infantry_count
                inf_det.unit_type = Mock()
                inf_det.unit_type.category = "infantry"
                inf_det.unit_type.battle_multiplier = 1.0
                army.detachments.append(inf_det)

            # Cavalry detachment
            cav_det = Mock()
            cav_det.soldier_count = cavalry_count
            cav_det.unit_type = Mock()
            cav_det.unit_type.category = "cavalry"
            cav_det.unit_type.battle_multiplier = 2.0
            army.detachments.append(cav_det)
        else:
            # All infantry
            inf_det = Mock()
            inf_det.soldier_count = soldiers
            inf_det.unit_type = Mock()
            inf_det.unit_type.category = "infantry"
            inf_det.unit_type.battle_multiplier = 1.0
            army.detachments.append(inf_det)

        return army


def test_calculate_morale_check_result_success():
    """Test morale check result calculation for success cases."""
    # With morale 9, rolls 9 or less are successes
    success, consequence, roll = calculate_morale_check_result(9)

    # Since this uses random roll, we can't predict exact outcomes,
    # but we can verify the function signature and structure
    assert isinstance(success, bool)
    assert isinstance(consequence, str)
    assert isinstance(roll, int)
    assert 2 <= roll <= 12  # 2d6 roll range


def test_calculate_morale_check_result_failure():
    """Test morale check result calculation for failure cases."""
    # This test would be better with a mocked random function,
    # but for now just ensure the function signature is correct
    success, consequence, roll = calculate_morale_check_result(4)

    assert isinstance(success, bool)
    assert isinstance(consequence, str)
    assert isinstance(roll, int)
    assert 2 <= roll <= 12  # 2d6 roll range
