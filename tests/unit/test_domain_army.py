"""Unit tests for army domain logic."""

from unittest.mock import Mock

from cataphract.domain.army import (
    apply_noncombatant_gains,
    calculate_total_detachments,
    can_split_army,
    validate_detachments_unsplittable,
)
from cataphract.models.army import Army, Detachment
from cataphract.models.commander import Trait


class TestDomainArmy:
    """Test cases for army domain logic."""

    def test_validate_detachments_unsplittable_valid(self):
        """Test validation passes for valid detachments."""
        det1 = Mock(spec=Detachment, soldier_count=100)
        det2 = Mock(spec=Detachment, soldier_count=200)

        result = validate_detachments_unsplittable([det1, det2])

        assert result is True

    def test_validate_detachments_unsplittable_invalid(self):
        """Test validation fails for detachment with zero soldiers."""
        det1 = Mock(spec=Detachment, soldier_count=100)
        det2 = Mock(spec=Detachment, soldier_count=0)

        result = validate_detachments_unsplittable([det1, det2])

        assert result is False

    def test_validate_detachments_unsplittable_empty(self):
        """Test validation passes for empty list."""
        result = validate_detachments_unsplittable([])

        assert result is True

    def test_calculate_total_detachments(self):
        """Test counting total detachments."""
        army = Mock(spec=Army)
        army.detachments = [
            Mock(spec=Detachment),
            Mock(spec=Detachment),
            Mock(spec=Detachment),
        ]

        result = calculate_total_detachments(army)

        assert result == 3

    def test_calculate_total_detachments_empty(self):
        """Test counting detachments for empty army."""
        army = Mock(spec=Army)
        army.detachments = []

        result = calculate_total_detachments(army)

        assert result == 0

    def test_can_split_army_valid(self):
        """Test valid army split."""
        army = Mock(spec=Army)
        army.detachments = [
            Mock(spec=Detachment),
            Mock(spec=Detachment),
            Mock(spec=Detachment),
        ]

        proposed = [Mock(spec=Detachment), Mock(spec=Detachment)]

        result = can_split_army(army, proposed)

        assert result is True

    def test_can_split_army_too_many_detachments(self):
        """Test split fails when taking all detachments."""
        army = Mock(spec=Army)
        army.detachments = [Mock(spec=Detachment), Mock(spec=Detachment)]

        proposed = [Mock(spec=Detachment), Mock(spec=Detachment)]

        result = can_split_army(army, proposed)

        assert result is False

    def test_can_split_army_empty_proposed(self):
        """Test split fails when proposing empty split."""
        army = Mock(spec=Army)
        army.detachments = [Mock(spec=Detachment), Mock(spec=Detachment)]

        proposed = []

        result = can_split_army(army, proposed)

        assert result is False

    def test_apply_noncombatant_gains_no_traits(self):
        """Test NC gains without Spartan trait."""
        army = Mock(spec=Army)
        army.noncombatant_count = 100

        apply_noncombatant_gains(army, 0.10, traits=None)

        assert army.noncombatant_count == 110

    def test_apply_noncombatant_gains_with_spartan(self):
        """Test NC gains with Spartan trait (halves gains)."""
        army = Mock(spec=Army)
        army.noncombatant_count = 100

        spartan_trait = Mock(spec=Trait)
        spartan_trait.name = "Spartan"

        apply_noncombatant_gains(army, 0.10, traits=[spartan_trait])

        assert army.noncombatant_count == 105  # 100 * (1 + 0.10/2)

    def test_apply_noncombatant_gains_with_other_traits(self):
        """Test NC gains with non-Spartan traits."""
        army = Mock(spec=Army)
        army.noncombatant_count = 100

        other_trait = Mock(spec=Trait)
        other_trait.name = "Logistician"

        apply_noncombatant_gains(army, 0.10, traits=[other_trait])

        assert army.noncombatant_count == 110  # Spartan not present

    def test_apply_noncombatant_gains_zero_increase(self):
        """Test NC gains with zero percentage increase."""
        army = Mock(spec=Army)
        army.noncombatant_count = 100

        apply_noncombatant_gains(army, 0.0, traits=None)

        assert army.noncombatant_count == 100

    def test_apply_noncombatant_gains_large_increase(self):
        """Test NC gains with large percentage increase."""
        army = Mock(spec=Army)
        army.noncombatant_count = 1000

        apply_noncombatant_gains(army, 0.50, traits=None)

        assert army.noncombatant_count == 1500  # 1000 * 1.5
