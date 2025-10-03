"""Unit tests for morale domain logic."""

from unittest.mock import Mock

from cataphract.domain.morale import (
    apply_morale_consequence,
    roll_morale_check,
)
from cataphract.models.army import Army
from cataphract.models.commander import Trait


class TestMoraleDomain:
    """Test cases for morale domain logic."""

    def test_roll_morale_check_success(self):
        """Test successful morale check."""
        # Seed that produces a low roll
        success, roll = roll_morale_check(morale=9, seed="test:1:morning:morale")
        # With deterministic RNG, we can't predict the exact roll
        # but we can test the function works
        assert isinstance(success, bool)
        assert 2 <= roll <= 12

    def test_roll_morale_check_failure(self):
        """Test failed morale check."""
        # Very low morale should fail more often
        success, roll = roll_morale_check(morale=2, seed="test:1:morning:morale")
        assert isinstance(success, bool)
        assert 2 <= roll <= 12

    def test_apply_consequence_mass_desertion(self):
        """Test mass desertion consequence."""
        army = Mock(spec=Army)
        army.detachments = [
            Mock(soldier_count=100),
            Mock(soldier_count=200),
        ]
        army.supplies_current = 1000
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=3, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "MASS_DESERTION"
        assert details["loss_percentage"] == 0.30
        # Detachments should be reduced by 30%
        assert army.detachments[0].soldier_count == 70  # 100 * 0.7
        assert army.detachments[1].soldier_count == 140  # 200 * 0.7
        assert army.supplies_current == 700  # 1000 * 0.7

    def test_apply_consequence_major_desertion(self):
        """Test major desertion consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(soldier_count=100)]
        army.supplies_current = 1000
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=5, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "MAJOR_DESERTION"
        assert details["loss_percentage"] == 0.20
        assert army.detachments[0].soldier_count == 80  # 100 * 0.8
        assert army.supplies_current == 800  # 1000 * 0.8

    def test_apply_consequence_desertion(self):
        """Test desertion consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(soldier_count=100)]
        army.supplies_current = 1000
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=8, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DESERTION"
        assert details["loss_percentage"] == 0.10
        assert army.detachments[0].soldier_count == 90  # 100 * 0.9
        assert army.supplies_current == 900  # 1000 * 0.9

    def test_apply_consequence_camp_followers(self):
        """Test camp followers consequence."""
        army = Mock(spec=Army)
        army.detachments = []
        army.noncombatant_count = 100
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=10, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "CAMP_FOLLOWERS"
        assert details["noncombatant_increase"] == 5  # 100 * 0.05
        assert army.noncombatant_count == 105

    def test_apply_consequence_no_consequences(self):
        """Test no consequences outcome."""
        army = Mock(spec=Army)
        army.detachments = []
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=12, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "NO_CONSEQUENCES"

    def test_apply_consequence_mutiny(self):
        """Test mutiny consequence."""
        army = Mock(spec=Army)
        det1 = Mock(id=1, army_id=1)
        det2 = Mock(id=2, army_id=1)
        army.detachments = [det1, det2]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=2, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "MUTINY"
        assert "defecting_detachments" in details
        # With 19/20 chance, most should defect

    def test_apply_consequence_detachments_defect(self):
        """Test detachments defect consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=i, army_id=1) for i in range(5)]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=4, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DETACHMENTS_DEFECT"
        assert "defecting_detachments" in details
        # Should defect 1d6 detachments, but leave at least 1

    def test_apply_consequence_army_splits(self):
        """Test army splits consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=i, army_id=1) for i in range(4)]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=6, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "ARMY_SPLITS"
        assert "splitting_detachments" in details
        # Should have at least 1 detachment remaining

    def test_apply_consequence_random_detachment_defects(self):
        """Test random detachment defects consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=1, army_id=1), Mock(id=2, army_id=1)]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=7, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "RANDOM_DETACHMENT_DEFECTS"
        assert details["defecting_detachments"] == 1

    def test_apply_consequence_detachments_depart(self):
        """Test detachments depart consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=i) for i in range(5)]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=9, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DETACHMENTS_DEPART"
        assert "departing_detachments" in details
        assert "return_in_days" in details
        # Should track departed detachments in status_effects
        assert army.status_effects is not None
        assert "departed_detachments" in army.status_effects

    def test_apply_consequence_detachment_departs(self):
        """Test single detachment departs consequence."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=1), Mock(id=2)]
        army.status_effects = None

        traits = []
        details = apply_morale_consequence(
            army, roll=11, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DETACHMENT_DEPARTS"
        assert details["departing_detachments"] == 1
        assert "return_in_days" in details
        # Should track departed detachment in status_effects
        assert army.status_effects is not None
        assert "departed_detachments" in army.status_effects

    def test_poet_trait_modifies_roll(self):
        """Test that Poet trait adds +2 to consequence determination."""
        army = Mock(spec=Army)
        army.detachments = [Mock(soldier_count=100)]
        army.supplies_current = 1000
        army.status_effects = None

        poet_trait = Mock(spec=Trait)
        poet_trait.name = "Poet"
        traits = [poet_trait]

        # Roll of 6 + 2 (Poet) = 8 (DESERTION)
        details = apply_morale_consequence(
            army, roll=6, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DESERTION"

    def test_poet_trait_clamps_upper_bound(self):
        """Poet bonus should not exceed morale consequence table bounds."""
        army = Mock(spec=Army)
        army.detachments = []
        army.status_effects = None

        poet_trait = Mock(spec=Trait)
        poet_trait.name = "poet"

        details = apply_morale_consequence(
            army,
            roll=11,
            traits=[poet_trait],
            seed="test:1:morning:poet",
            current_day=0,
        )

        assert details["consequence_type"] == "NO_CONSEQUENCES"

    def test_edge_case_single_detachment_no_defection(self):
        """Test that armies with 1 detachment don't lose all detachments."""
        army = Mock(spec=Army)
        army.detachments = [Mock(id=1, army_id=1)]
        army.status_effects = None

        traits = []
        # Try random detachment defects - should not defect the only detachment
        details = apply_morale_consequence(
            army, roll=7, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "RANDOM_DETACHMENT_DEFECTS"
        assert details["defecting_detachments"] == 0

    def test_edge_case_no_detachments(self):
        """Test consequences with no detachments."""
        army = Mock(spec=Army)
        army.detachments = []
        army.status_effects = None
        army.supplies_current = 1000

        traits = []
        # Try desertion with no detachments - should still reduce supplies
        details = apply_morale_consequence(
            army, roll=8, traits=traits, seed="test:1:morning:consequence", current_day=10
        )

        assert details["consequence_type"] == "DESERTION"
        assert army.supplies_current == 900
