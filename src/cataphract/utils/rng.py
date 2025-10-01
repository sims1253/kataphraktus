"""Deterministic Random Number Generator (RNG) system for Cataphract.

This module provides deterministic random number generation with full audit trail
support. All randomness is seeded from game state (game_id, day, part, context)
to ensure:
- Reproducibility: Same seed always produces same results
- Fairness: No hidden randomness
- Bug reproduction: Exact game state replay
- Audit trail: All random events fully logged

Examples:
    >>> seed = generate_seed(game_id=1, day=42, part="morning", context="morale_check")
    >>> result = roll_dice(seed, "2d6")
    >>> print(result)
    {'notation': '2d6', 'rolls': [3, 5], 'total': 8, 'seed': '1:42:morning:morale_check'}

    >>> result = random_choice(seed, ["attack", "defend", "retreat"])
    >>> print(result)
    {'choice': 'defend', 'index': 1, 'seed': '1:42:morning:morale_check'}
"""

import hashlib
import random
import re
from functools import cache
from typing import Any


def generate_seed(game_id: int, day: int, part: str, context: str) -> str:
    """Generate deterministic seed from game state.

    Creates a unique seed string from game state components. The seed format
    ensures that the same game state always produces the same random results.

    Format: "game_id:day:part:context"

    Args:
        game_id: Current game ID (unique per campaign)
        day: Current game day (increments daily)
        part: Current daypart ('morning', 'midday', 'evening', 'night')
        context: What the roll is for (e.g., 'morale_check_army_15', 'battle_roll')

    Returns:
        Seed string for RNG in format "game_id:day:part:context"

    Examples:
        >>> generate_seed(1, 42, "morning", "morale_check_army_15")
        '1:42:morning:morale_check_army_15'

        >>> generate_seed(5, 100, "evening", "weather_generation")
        '5:100:evening:weather_generation'

    Raises:
        ValueError: If game_id or day is negative
    """
    if game_id < 0:
        raise ValueError(f"game_id must be non-negative, got {game_id}")
    if day < 0:
        raise ValueError(f"day must be non-negative, got {day}")

    return f"{game_id}:{day}:{part}:{context}"


def _seed_to_int(seed: str) -> int:
    """Convert seed string to a stable 64-bit integer for random.Random().

    Args:
        seed: Seed string

    Returns:
        64-bit integer derived from SHA-256(seed)
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    # Use first 8 bytes for a 64-bit integer
    return int.from_bytes(digest[:8], "big", signed=False)


def _parse_dice_notation(notation: str) -> tuple[int, int]:
    """Parse dice notation like '2d6' into (num_dice, num_sides).

    Args:
        notation: Dice notation string (e.g., "2d6", "1d20", "3d6")

    Returns:
        Tuple of (number_of_dice, number_of_sides)

    Raises:
        ValueError: If notation is invalid or values are non-positive

    Examples:
        >>> _parse_dice_notation("2d6")
        (2, 6)

        >>> _parse_dice_notation("1d20")
        (1, 20)
    """
    match = re.match(r"^(\d+)d(\d+)$", notation.lower())
    if not match:
        raise ValueError(
            f"Invalid dice notation: '{notation}'. Expected format: NdM (e.g., '2d6', '1d20')"
        )

    num_dice = int(match.group(1))
    num_sides = int(match.group(2))

    if num_dice <= 0:
        raise ValueError(f"Number of dice must be positive, got {num_dice}")
    if num_sides <= 0:
        raise ValueError(f"Number of sides must be positive, got {num_sides}")

    return num_dice, num_sides


def roll_dice(seed: str, notation: str = "2d6") -> dict[str, Any]:
    """Roll dice with deterministic seed.

    Rolls dice using the specified notation and seed. The same seed and notation
    will always produce the same results.

    Args:
        seed: Deterministic seed string (from generate_seed)
        notation: Dice notation (e.g., "2d6", "1d20", "3d6")

    Returns:
        Dictionary containing:
            - notation: The dice notation used
            - rolls: List of individual die rolls
            - total: Sum of all rolls
            - seed: The seed used

    Examples:
        >>> seed = generate_seed(1, 1, "morning", "test")
        >>> result = roll_dice(seed, "2d6")
        >>> result['notation']
        '2d6'
        >>> len(result['rolls'])
        2
        >>> result['total'] == sum(result['rolls'])
        True

    Raises:
        ValueError: If dice notation is invalid
    """
    num_dice, num_sides = _parse_dice_notation(notation)

    rng = random.Random(_seed_to_int(seed))
    rolls = [rng.randint(1, num_sides) for _ in range(num_dice)]

    return {
        "notation": notation,
        "rolls": rolls,
        "total": sum(rolls),
        "seed": seed,
    }


def random_choice(seed: str, options: list[Any]) -> dict[str, Any]:
    """Choose randomly from options with deterministic seed.

    Selects one item from the options list using the seed. The same seed
    and options will always produce the same choice.

    Args:
        seed: Deterministic seed string
        options: List of options to choose from (must be non-empty)

    Returns:
        Dictionary containing:
            - choice: The selected option
            - index: Index of the selected option
            - seed: The seed used

    Examples:
        >>> seed = generate_seed(1, 1, "morning", "test")
        >>> result = random_choice(seed, ["A", "B", "C"])
        >>> result['choice'] in ["A", "B", "C"]
        True
        >>> 0 <= result['index'] < 3
        True

    Raises:
        ValueError: If options list is empty
    """
    if not options:
        raise ValueError("options list cannot be empty")

    rng = random.Random(_seed_to_int(seed))
    index = rng.randint(0, len(options) - 1)

    return {
        "choice": options[index],
        "index": index,
        "seed": seed,
    }


def random_int(seed: str, min_val: int, max_val: int) -> dict[str, Any]:
    """Generate random integer in range with deterministic seed.

    Generates a random integer between min_val and max_val (inclusive) using
    the seed. The same seed and range will always produce the same value.

    Args:
        seed: Deterministic seed string
        min_val: Minimum value (inclusive)
        max_val: Maximum value (inclusive)

    Returns:
        Dictionary containing:
            - value: The random integer
            - min: The minimum value
            - max: The maximum value
            - seed: The seed used

    Examples:
        >>> seed = generate_seed(1, 1, "morning", "test")
        >>> result = random_int(seed, 1, 100)
        >>> 1 <= result['value'] <= 100
        True
        >>> result['min']
        1
        >>> result['max']
        100

    Raises:
        ValueError: If min_val > max_val
    """
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) cannot be greater than max_val ({max_val})")

    rng = random.Random(_seed_to_int(seed))
    value = rng.randint(min_val, max_val)

    return {
        "value": value,
        "min": min_val,
        "max": max_val,
        "seed": seed,
    }


@cache
def _dice_pmf(num_dice: int, num_sides: int) -> dict[int, int]:
    """Compute the PMF (counts) for the sum of `num_dice` d`num_sides`.

    Returns a mapping total -> count of outcomes.
    """
    pmf: dict[int, int] = {0: 1}
    for _ in range(num_dice):
        new: dict[int, int] = {}
        for total, count in pmf.items():
            for face in range(1, num_sides + 1):
                new[total + face] = new.get(total + face, 0) + count
        pmf = new
    return pmf


@cache
def _dice_threshold_for_probability(probability: float, num_dice: int, num_sides: int) -> int:
    """Find minimal target T such that P(roll >= T) >= probability for NdM.

    For probability=0.0, returns max_roll + 1 (always fail). For probability=1.0,
    returns min_roll (always succeed).
    """
    min_roll = num_dice
    max_roll = num_dice * num_sides

    if probability <= 0.0:
        return max_roll + 1
    if probability >= 1.0:
        return min_roll

    pmf = _dice_pmf(num_dice, num_sides)
    total_outcomes = num_sides**num_dice

    # Accumulate from high to low until we reach requested probability
    cumulative = 0.0
    for target in range(max_roll, min_roll - 1, -1):
        cumulative += pmf.get(target, 0) / total_outcomes
        if cumulative >= probability:
            return target

    # Fallback (should not happen): require impossible target
    return max_roll + 1


def check_success(seed: str, probability: float, dice_notation: str = "1d6") -> dict[str, Any]:
    """Check if random event succeeds based on probability.

    Rolls dice and checks if the result meets the target threshold based on
    the given probability. Uses dice rolls rather than uniform random to
    match game mechanics.

    Common patterns:
        - probability=0.5, dice="1d6" -> success on 4+ (3-in-6 chance)
        - probability=1/6, dice="1d6" -> success on 6 (1-in-6 chance)
        - probability=1/3, dice="2d6" -> success on 10+ (approximately)

    Args:
        seed: Deterministic seed string
        probability: Desired success probability (0.0 to 1.0)
        dice_notation: Dice notation to use for the check

    Returns:
        Dictionary containing:
            - success: Whether the check succeeded
            - roll: The dice roll result
            - target: The target number needed to succeed
            - probability: The requested probability
            - seed: The seed used

    Examples:
        >>> seed = generate_seed(1, 1, "morning", "test")
        >>> result = check_success(seed, 0.5, "1d6")
        >>> isinstance(result['success'], bool)
        True
        >>> 1 <= result['roll'] <= 6
        True

    Raises:
        ValueError: If probability not in [0.0, 1.0] or dice notation invalid
    """
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be between 0.0 and 1.0, got {probability}")

    num_dice, num_sides = _parse_dice_notation(dice_notation)

    # Compute exact threshold for NdM using PMF/CDF
    target = _dice_threshold_for_probability(probability, num_dice, num_sides)

    # Roll the dice
    roll_result = roll_dice(seed, dice_notation)
    roll = roll_result["total"]

    return {
        "success": roll >= target,
        "roll": roll,
        "target": target,
        "probability": probability,
        "seed": seed,
    }
