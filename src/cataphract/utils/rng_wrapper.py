"""Wrapper functions for rng to preserve backward compatibility."""

from cataphract.utils.rng import generate_seed, roll_dice


def roll_dice_old(num_dice: int, num_sides: int) -> tuple[int, int, int]:
    """Backward compatible roll_dice function that mimics the old API.

    Args:
        num_dice: Number of dice to roll
        num_sides: Number of sides on each die

    Returns:
        Tuple of (min_possible, max_possible, actual_roll)
    """
    # Generate a deterministic seed for backward compatibility
    seed = generate_seed(num_dice, num_sides, "morning", "backward_compat")
    notation = f"{num_dice}d{num_sides}"
    result = roll_dice(seed, notation)

    min_possible = num_dice * 1
    max_possible = num_dice * num_sides
    actual_roll = result["total"]

    return (min_possible, max_possible, actual_roll)
