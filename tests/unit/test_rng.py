"""Comprehensive tests for deterministic RNG system.

Tests cover:
- Determinism (same seed -> same result)
- Variety (different seeds -> different results)
- All dice notations
- Edge cases and validation
- Audit trail structure
- Property-based tests
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cataphract.utils.rng import (
    check_success,
    generate_seed,
    random_choice,
    random_int,
    roll_dice,
)


class TestGenerateSeed:
    """Tests for generate_seed function."""

    def test_basic_seed_generation(self):
        """Test basic seed generation with valid inputs."""
        seed = generate_seed(1, 42, "morning", "morale_check")
        assert seed == "1:42:morning:morale_check"

    def test_seed_format(self):
        """Test that seed follows the expected format."""
        seed = generate_seed(5, 100, "evening", "battle_roll_army_3")
        parts = seed.split(":")
        assert len(parts) == 4
        assert parts[0] == "5"
        assert parts[1] == "100"
        assert parts[2] == "evening"
        assert parts[3] == "battle_roll_army_3"

    def test_different_parameters_produce_different_seeds(self):
        """Test that different parameters produce unique seeds."""
        seed1 = generate_seed(1, 1, "morning", "test")
        seed2 = generate_seed(2, 1, "morning", "test")
        seed3 = generate_seed(1, 2, "morning", "test")
        seed4 = generate_seed(1, 1, "evening", "test")
        seed5 = generate_seed(1, 1, "morning", "other")

        seeds = {seed1, seed2, seed3, seed4, seed5}
        assert len(seeds) == 5, "All seeds should be unique"

    def test_negative_game_id_raises_error(self):
        """Test that negative game_id raises ValueError."""
        with pytest.raises(ValueError, match="game_id must be non-negative"):
            generate_seed(-1, 1, "morning", "test")

    def test_negative_day_raises_error(self):
        """Test that negative day raises ValueError."""
        with pytest.raises(ValueError, match="day must be non-negative"):
            generate_seed(1, -1, "morning", "test")

    def test_zero_values_allowed(self):
        """Test that zero values are allowed for game_id and day."""
        seed = generate_seed(0, 0, "morning", "test")
        assert seed == "0:0:morning:test"

    def test_large_values(self):
        """Test with large game_id and day values."""
        seed = generate_seed(999999, 99999, "night", "long_context_string_test")
        assert seed == "999999:99999:night:long_context_string_test"

    @given(
        game_id=st.integers(min_value=0, max_value=10000),
        day=st.integers(min_value=0, max_value=10000),
        part=st.text(min_size=1),
        context=st.text(min_size=1),
    )
    def test_seed_generation_properties(self, game_id, day, part, context):
        """Property-based test: seed generation always produces valid format."""
        seed = generate_seed(game_id, day, part, context)
        assert isinstance(seed, str)
        assert f"{game_id}:{day}:{part}:{context}" == seed


class TestRollDice:
    """Tests for roll_dice function."""

    def test_determinism_same_seed_same_result(self):
        """Test that same seed produces same dice rolls."""
        seed = generate_seed(1, 1, "morning", "test")

        result1 = roll_dice(seed, "2d6")
        result2 = roll_dice(seed, "2d6")

        assert result1 == result2
        assert result1["rolls"] == result2["rolls"]
        assert result1["total"] == result2["total"]

    def test_different_seeds_different_results(self):
        """Test that different seeds produce different results."""
        seed1 = generate_seed(1, 1, "morning", "test1")
        seed2 = generate_seed(1, 1, "morning", "test2")

        roll_dice(seed1, "2d6")
        roll_dice(seed2, "2d6")

        # With high probability, different seeds give different results
        # We'll run multiple rolls to verify variety
        assert seed1 != seed2
        # At least one difference in 10 rolls would be expected
        differences = 0
        for i in range(10):
            r1 = roll_dice(generate_seed(1, i, "morning", "a"), "2d6")
            r2 = roll_dice(generate_seed(1, i, "morning", "b"), "2d6")
            if r1["total"] != r2["total"]:
                differences += 1
        assert differences > 0, "Different seeds should produce some different results"

    def test_2d6_notation(self):
        """Test standard 2d6 notation."""
        seed = generate_seed(1, 1, "morning", "test")
        result = roll_dice(seed, "2d6")

        assert result["notation"] == "2d6"
        assert len(result["rolls"]) == 2
        assert all(1 <= roll <= 6 for roll in result["rolls"])
        assert result["total"] == sum(result["rolls"])
        assert result["seed"] == seed

    def test_1d20_notation(self):
        """Test 1d20 notation."""
        seed = generate_seed(1, 2, "morning", "test")
        result = roll_dice(seed, "1d20")

        assert result["notation"] == "1d20"
        assert len(result["rolls"]) == 1
        assert 1 <= result["rolls"][0] <= 20
        assert result["total"] == result["rolls"][0]

    def test_3d6_notation(self):
        """Test 3d6 notation."""
        seed = generate_seed(1, 3, "morning", "test")
        result = roll_dice(seed, "3d6")

        assert result["notation"] == "3d6"
        assert len(result["rolls"]) == 3
        assert all(1 <= roll <= 6 for roll in result["rolls"])
        assert result["total"] == sum(result["rolls"])

    def test_various_dice_notations(self):
        """Test various valid dice notations."""
        seed = generate_seed(1, 4, "morning", "test")

        notations = ["1d4", "1d6", "1d8", "1d10", "1d12", "1d100", "4d6", "10d10"]
        for notation in notations:
            result = roll_dice(seed, notation)
            assert result["notation"] == notation
            assert len(result["rolls"]) > 0
            assert result["total"] > 0

    def test_invalid_notation_raises_error(self):
        """Test that invalid notation raises ValueError."""
        seed = generate_seed(1, 5, "morning", "test")

        invalid_notations = [
            "2x6",  # Wrong separator
            "d6",  # Missing number of dice
            "2d",  # Missing number of sides
            "2.5d6",  # Float dice
            "2d6.5",  # Float sides
            "",  # Empty string
            "abc",  # Non-numeric
        ]

        for notation in invalid_notations:
            with pytest.raises(ValueError, match="Invalid dice notation"):
                roll_dice(seed, notation)

    def test_zero_dice_raises_error(self):
        """Test that 0 dice raises ValueError."""
        seed = generate_seed(1, 6, "morning", "test")
        with pytest.raises(ValueError, match="Number of dice must be positive"):
            roll_dice(seed, "0d6")

    def test_zero_sides_raises_error(self):
        """Test that 0-sided die raises ValueError."""
        seed = generate_seed(1, 7, "morning", "test")
        with pytest.raises(ValueError, match="Number of sides must be positive"):
            roll_dice(seed, "2d0")

    def test_negative_dice_raises_error(self):
        """Test that negative dice raises ValueError."""
        seed = generate_seed(1, 8, "morning", "test")
        with pytest.raises(ValueError, match="Invalid dice notation"):
            roll_dice(seed, "-2d6")

    def test_case_insensitive(self):
        """Test that notation is case-insensitive."""
        seed = generate_seed(1, 9, "morning", "test")
        result1 = roll_dice(seed, "2d6")
        result2 = roll_dice(seed, "2D6")

        assert result1["rolls"] == result2["rolls"]

    def test_default_notation(self):
        """Test that default notation is 2d6."""
        seed = generate_seed(1, 10, "morning", "test")
        result = roll_dice(seed)

        assert result["notation"] == "2d6"
        assert len(result["rolls"]) == 2

    def test_audit_trail_structure(self):
        """Test that result contains all required audit trail fields."""
        seed = generate_seed(1, 11, "morning", "test")
        result = roll_dice(seed, "2d6")

        assert "notation" in result
        assert "rolls" in result
        assert "total" in result
        assert "seed" in result

    def test_multiple_rolls_with_same_seed_sequence(self):
        """Test reproducibility across multiple roll sequences."""
        base_seed = "1:1:morning:base"

        # First sequence
        results1 = [roll_dice(f"{base_seed}_roll_{i}", "2d6") for i in range(5)]

        # Second sequence with same seeds
        results2 = [roll_dice(f"{base_seed}_roll_{i}", "2d6") for i in range(5)]

        assert results1 == results2

    @given(
        num_dice=st.integers(min_value=1, max_value=10),
        num_sides=st.integers(min_value=2, max_value=100),
    )
    def test_dice_roll_properties(self, num_dice, num_sides):
        """Property-based test: dice rolls are always in valid range."""
        seed = generate_seed(1, 1, "morning", "property_test")
        notation = f"{num_dice}d{num_sides}"

        result = roll_dice(seed, notation)

        assert len(result["rolls"]) == num_dice
        assert all(1 <= roll <= num_sides for roll in result["rolls"])
        assert result["total"] == sum(result["rolls"])
        assert num_dice <= result["total"] <= num_dice * num_sides


class TestRandomChoice:
    """Tests for random_choice function."""

    def test_determinism_same_seed_same_choice(self):
        """Test that same seed produces same choice."""
        seed = generate_seed(1, 1, "morning", "test")
        options = ["A", "B", "C", "D"]

        result1 = random_choice(seed, options)
        result2 = random_choice(seed, options)

        assert result1 == result2
        assert result1["choice"] == result2["choice"]
        assert result1["index"] == result2["index"]

    def test_different_seeds_can_produce_different_choices(self):
        """Test that different seeds can produce different choices."""
        options = ["A", "B", "C"]

        # Generate many choices with different seeds
        choices = [
            random_choice(generate_seed(1, i, "morning", "test"), options)["choice"]
            for i in range(50)
        ]

        # Should have variety (at least 2 different choices in 50 rolls)
        unique_choices = set(choices)
        assert len(unique_choices) >= 2

    def test_choice_from_list(self):
        """Test choosing from a list of options."""
        seed = generate_seed(1, 2, "morning", "test")
        options = ["attack", "defend", "retreat"]

        result = random_choice(seed, options)

        assert result["choice"] in options
        assert 0 <= result["index"] < len(options)
        assert result["choice"] == options[result["index"]]
        assert result["seed"] == seed

    def test_choice_from_numbers(self):
        """Test choosing from numeric options."""
        seed = generate_seed(1, 3, "morning", "test")
        options = [1, 2, 3, 4, 5]

        result = random_choice(seed, options)

        assert result["choice"] in options
        assert result["index"] in range(len(options))

    def test_choice_from_mixed_types(self):
        """Test choosing from mixed type options."""
        seed = generate_seed(1, 4, "morning", "test")
        options = [1, "two", 3.0, None, True]

        result = random_choice(seed, options)

        assert result["choice"] in options

    def test_single_option(self):
        """Test that single option always returns that option."""
        seed = generate_seed(1, 5, "morning", "test")
        options = ["only"]

        result = random_choice(seed, options)

        assert result["choice"] == "only"
        assert result["index"] == 0

    def test_empty_list_raises_error(self):
        """Test that empty options list raises ValueError."""
        seed = generate_seed(1, 6, "morning", "test")
        with pytest.raises(ValueError, match="options list cannot be empty"):
            random_choice(seed, [])

    def test_large_option_list(self):
        """Test choosing from large list."""
        seed = generate_seed(1, 7, "morning", "test")
        options = list(range(1000))

        result = random_choice(seed, options)

        assert result["choice"] in options
        assert 0 <= result["index"] < 1000

    def test_audit_trail_structure(self):
        """Test that result contains all required audit trail fields."""
        seed = generate_seed(1, 8, "morning", "test")
        options = ["A", "B", "C"]

        result = random_choice(seed, options)

        assert "choice" in result
        assert "index" in result
        assert "seed" in result

    def test_distribution_over_many_rolls(self):
        """Test that choices are reasonably distributed."""
        options = ["A", "B", "C"]
        choices = [
            random_choice(generate_seed(1, i, "morning", "test"), options)["choice"]
            for i in range(300)
        ]

        # Count occurrences
        counts = {opt: choices.count(opt) for opt in options}

        # Each option should appear at least 50 times in 300 rolls (rough check)
        # Expected is 100 each, but allowing for variance
        for opt in options:
            assert counts[opt] >= 50, f"Option {opt} only appeared {counts[opt]} times"

    @given(
        list_size=st.integers(min_value=1, max_value=100),
    )
    def test_random_choice_properties(self, list_size):
        """Property-based test: choice is always valid."""
        seed = generate_seed(1, 1, "morning", "property_test")
        options = list(range(list_size))

        result = random_choice(seed, options)

        assert result["choice"] in options
        assert 0 <= result["index"] < list_size
        assert result["choice"] == options[result["index"]]


class TestRandomInt:
    """Tests for random_int function."""

    def test_determinism_same_seed_same_value(self):
        """Test that same seed produces same integer."""
        seed = generate_seed(1, 1, "morning", "test")

        result1 = random_int(seed, 1, 100)
        result2 = random_int(seed, 1, 100)

        assert result1 == result2
        assert result1["value"] == result2["value"]

    def test_different_seeds_can_produce_different_values(self):
        """Test that different seeds can produce different values."""
        values = [
            random_int(generate_seed(1, i, "morning", "test"), 1, 100)["value"] for i in range(50)
        ]

        # Should have variety (at least 10 different values in 50 rolls)
        unique_values = set(values)
        assert len(unique_values) >= 10

    def test_value_in_range(self):
        """Test that generated value is in specified range."""
        seed = generate_seed(1, 2, "morning", "test")
        result = random_int(seed, 10, 20)

        assert 10 <= result["value"] <= 20
        assert result["min"] == 10
        assert result["max"] == 20
        assert result["seed"] == seed

    def test_min_equals_max(self):
        """Test that min=max always returns that value."""
        seed = generate_seed(1, 3, "morning", "test")
        result = random_int(seed, 42, 42)

        assert result["value"] == 42

    def test_large_range(self):
        """Test with large value range."""
        seed = generate_seed(1, 4, "morning", "test")
        result = random_int(seed, 1, 1000000)

        assert 1 <= result["value"] <= 1000000

    def test_negative_values(self):
        """Test with negative ranges."""
        seed = generate_seed(1, 5, "morning", "test")
        result = random_int(seed, -100, -50)

        assert -100 <= result["value"] <= -50

    def test_range_crossing_zero(self):
        """Test range that crosses zero."""
        seed = generate_seed(1, 6, "morning", "test")
        result = random_int(seed, -50, 50)

        assert -50 <= result["value"] <= 50

    def test_min_greater_than_max_raises_error(self):
        """Test that min > max raises ValueError."""
        seed = generate_seed(1, 7, "morning", "test")
        with pytest.raises(ValueError, match=r"min_val.*cannot be greater than max_val"):
            random_int(seed, 100, 50)

    def test_audit_trail_structure(self):
        """Test that result contains all required audit trail fields."""
        seed = generate_seed(1, 8, "morning", "test")
        result = random_int(seed, 1, 100)

        assert "value" in result
        assert "min" in result
        assert "max" in result
        assert "seed" in result

    def test_distribution_over_many_rolls(self):
        """Test that values are reasonably distributed."""
        values = [
            random_int(generate_seed(1, i, "morning", "test"), 1, 10)["value"] for i in range(1000)
        ]

        # Count occurrences of each value (1-10)
        counts = {i: values.count(i) for i in range(1, 11)}

        # Each value should appear roughly 100 times (allow 40-160 range)
        for val in range(1, 11):
            assert 40 <= counts[val] <= 160, (
                f"Value {val} appeared {counts[val]} times (expected ~100)"
            )

    @given(
        min_val=st.integers(min_value=-1000, max_value=1000),
        max_val=st.integers(min_value=-1000, max_value=1000),
    )
    def test_random_int_properties(self, min_val, max_val):
        """Property-based test: generated int is always in valid range."""
        if min_val > max_val:
            min_val, max_val = max_val, min_val

        seed = generate_seed(1, 1, "morning", "property_test")
        result = random_int(seed, min_val, max_val)

        assert min_val <= result["value"] <= max_val
        assert result["min"] == min_val
        assert result["max"] == max_val


class TestCheckSuccess:
    """Tests for check_success function."""

    def test_determinism_same_seed_same_result(self):
        """Test that same seed produces same success check."""
        seed = generate_seed(1, 1, "morning", "test")

        result1 = check_success(seed, 0.5, "1d6")
        result2 = check_success(seed, 0.5, "1d6")

        assert result1 == result2

    def test_success_check_structure(self):
        """Test that result contains all required fields."""
        seed = generate_seed(1, 2, "morning", "test")
        result = check_success(seed, 0.5, "1d6")

        assert "success" in result
        assert "roll" in result
        assert "target" in result
        assert "probability" in result
        assert "seed" in result

        assert isinstance(result["success"], bool)
        assert isinstance(result["roll"], int)
        assert isinstance(result["target"], int)
        assert result["probability"] == 0.5
        assert result["seed"] == seed

    def test_probability_zero_always_fails(self):
        """Test that probability 0 always fails."""
        results = [
            check_success(generate_seed(1, i, "morning", "test"), 0.0, "1d6") for i in range(20)
        ]

        assert all(not result["success"] for result in results)

    def test_probability_one_always_succeeds(self):
        """Test that probability 1 always succeeds."""
        results = [
            check_success(generate_seed(1, i, "morning", "test"), 1.0, "1d6") for i in range(20)
        ]

        assert all(result["success"] for result in results)

    def test_probability_half_approximately_half_success(self):
        """Test that probability 0.5 gives roughly 50% success rate."""
        results = [
            check_success(generate_seed(1, i, "morning", "test"), 0.5, "2d6") for i in range(200)
        ]

        success_count = sum(1 for r in results if r["success"])
        success_rate = success_count / len(results)

        # Should be roughly 50%, allow 35-65% range for statistical variance
        assert 0.35 <= success_rate <= 0.65, (
            f"Success rate {success_rate:.2%} outside expected range"
        )

    def test_different_probabilities(self):
        """Test various probability values."""
        probabilities = [0.1, 0.25, 0.5, 0.75, 0.9]

        for prob in probabilities:
            results = [
                check_success(generate_seed(1, i, "morning", f"test_{prob}"), prob, "2d6")
                for i in range(100)
            ]

            success_count = sum(1 for r in results if r["success"])
            success_rate = success_count / len(results)

            # Allow generous margin for small sample
            assert prob - 0.2 <= success_rate <= prob + 0.2

    def test_roll_in_valid_range(self):
        """Test that roll is always in valid dice range."""
        seed = generate_seed(1, 3, "morning", "test")
        result = check_success(seed, 0.5, "2d6")

        assert 2 <= result["roll"] <= 12

    def test_target_calculation(self):
        """Test that target is calculated reasonably."""
        seed = generate_seed(1, 4, "morning", "test")

        # For 1d6 with prob 0.5, target should be around 4
        result = check_success(seed, 0.5, "1d6")
        assert 1 <= result["target"] <= 7

    def test_different_dice_notations(self):
        """Test success check with various dice notations."""
        seed = generate_seed(1, 5, "morning", "test")

        notations = ["1d6", "2d6", "3d6", "1d20"]
        for notation in notations:
            result = check_success(seed, 0.5, notation)
            assert isinstance(result["success"], bool)
            assert result["roll"] > 0

    def test_invalid_probability_raises_error(self):
        """Test that invalid probability raises ValueError."""
        seed = generate_seed(1, 6, "morning", "test")

        with pytest.raises(ValueError, match=r"probability must be between 0.0 and 1.0"):
            check_success(seed, -0.1, "1d6")

        with pytest.raises(ValueError, match=r"probability must be between 0.0 and 1.0"):
            check_success(seed, 1.5, "1d6")

    def test_invalid_dice_notation_raises_error(self):
        """Test that invalid dice notation raises ValueError."""
        seed = generate_seed(1, 7, "morning", "test")

        with pytest.raises(ValueError, match="Invalid dice notation"):
            check_success(seed, 0.5, "invalid")

    def test_default_dice_notation(self):
        """Test default dice notation is 1d6."""
        seed = generate_seed(1, 8, "morning", "test")
        result = check_success(seed, 0.5)

        assert 1 <= result["roll"] <= 6

    def test_edge_case_single_sided_die(self):
        """Test with 1d1 (always rolls 1)."""
        seed = generate_seed(1, 9, "morning", "test")

        # With 1d1, prob 0.5 should have target of 1, always succeeding
        result = check_success(seed, 0.5, "1d1")
        assert result["roll"] == 1

    def test_audit_trail_structure(self):
        """Test that result matches audit trail requirements."""
        seed = generate_seed(1, 10, "morning", "morale_check")
        result = check_success(seed, 0.5, "2d6")

        # Verify structure matches rand_source schema expectations
        assert "seed" in result
        assert "roll" in result
        assert result["seed"] == seed

    @given(
        probability=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_check_success_properties(self, probability):
        """Property-based test: success check always returns valid structure."""
        seed = generate_seed(1, 1, "morning", "property_test")

        result = check_success(seed, probability, "1d6")

        assert isinstance(result["success"], bool)
        assert 1 <= result["roll"] <= 6
        assert 1 <= result["target"] <= 7
        assert result["probability"] == probability


class TestIntegration:
    """Integration tests for the complete RNG system."""

    def test_full_workflow_example(self):
        """Test a complete workflow using all RNG functions."""
        # Generate seed for a morale check on day 42
        seed = generate_seed(game_id=1, day=42, part="morning", context="morale_check_army_15")

        # Roll 2d6 for the morale check
        dice_result = roll_dice(seed, "2d6")
        assert 2 <= dice_result["total"] <= 12

        # Check if army passes morale (50% chance)
        success_seed = generate_seed(1, 42, "morning", "morale_success_army_15")
        success_result = check_success(success_seed, 0.5, "2d6")
        assert isinstance(success_result["success"], bool)

        # If failed, choose random reaction
        reaction_seed = generate_seed(1, 42, "morning", "morale_reaction_army_15")
        reactions = ["retreat", "hold", "rout"]
        reaction_result = random_choice(reaction_seed, reactions)
        assert reaction_result["choice"] in reactions

        # Determine casualties
        casualty_seed = generate_seed(1, 42, "morning", "casualties_army_15")
        casualty_result = random_int(casualty_seed, 10, 50)
        assert 10 <= casualty_result["value"] <= 50

    def test_reproducible_battle_sequence(self):
        """Test that a sequence of battle actions is reproducible."""

        def simulate_battle_round(game_id: int, day: int, round_num: int) -> dict:
            """Simulate one round of battle."""
            base = f"battle_round_{round_num}"

            # Initiative roll
            init_seed = generate_seed(game_id, day, "midday", f"{base}_initiative")
            initiative = roll_dice(init_seed, "1d6")

            # Attack roll
            attack_seed = generate_seed(game_id, day, "midday", f"{base}_attack")
            attack = roll_dice(attack_seed, "2d6")

            # Defense roll
            defense_seed = generate_seed(game_id, day, "midday", f"{base}_defense")
            defense = roll_dice(defense_seed, "2d6")

            # Determine outcome
            outcome_seed = generate_seed(game_id, day, "midday", f"{base}_outcome")
            outcomes = ["attacker_wins", "defender_wins", "stalemate"]
            outcome = random_choice(outcome_seed, outcomes)

            return {
                "initiative": initiative,
                "attack": attack,
                "defense": defense,
                "outcome": outcome,
            }

        # Run battle twice with same parameters
        battle1 = simulate_battle_round(game_id=5, day=100, round_num=1)
        battle2 = simulate_battle_round(game_id=5, day=100, round_num=1)

        # Results should be identical
        assert battle1 == battle2

    def test_different_contexts_produce_variety(self):
        """Test that different contexts in the same game state produce variety."""
        game_id, day, part = 1, 50, "evening"

        contexts = [
            "weather",
            "morale_army_1",
            "morale_army_2",
            "foraging_result",
            "messenger_delay",
        ]

        results = []
        for context in contexts:
            seed = generate_seed(game_id, day, part, context)
            result = roll_dice(seed, "2d6")
            results.append(result["total"])

        # Should have some variety (not all the same)
        assert len(set(results)) > 1

    def test_audit_trail_json_serializable(self):
        """Test that all results can be serialized to JSON."""
        import json  # noqa: PLC0415

        seed = generate_seed(1, 1, "morning", "test")

        # Test all function results
        dice = roll_dice(seed, "2d6")
        choice = random_choice(seed, ["A", "B", "C"])
        rand = random_int(seed, 1, 100)
        success = check_success(seed, 0.5, "1d6")

        # All should be JSON serializable
        assert json.dumps(dice)
        assert json.dumps(choice)
        assert json.dumps(rand)
        assert json.dumps(success)

    def test_seed_components_independence(self):
        """Test that each seed component independently affects randomness."""
        base_roll = roll_dice(generate_seed(1, 1, "morning", "test"), "2d6")["total"]

        # Change each component independently
        diff_game = roll_dice(generate_seed(2, 1, "morning", "test"), "2d6")["total"]
        diff_day = roll_dice(generate_seed(1, 2, "morning", "test"), "2d6")["total"]
        diff_part = roll_dice(generate_seed(1, 1, "evening", "test"), "2d6")["total"]
        diff_context = roll_dice(generate_seed(1, 1, "morning", "other"), "2d6")["total"]

        # At least some should be different (with high probability)
        different_values = {base_roll, diff_game, diff_day, diff_part, diff_context}
        assert len(different_values) > 1
