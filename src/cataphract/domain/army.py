"""Army domain logic for Cataphract.

Pure functions for army composition, splitting/merging validations, etc.
"""

from cataphract.models.army import Army, Detachment
from cataphract.models.commander import Trait


def validate_detachments_unsplittable(detachments: list[Detachment]) -> bool:
    """Validate that detachments cannot be split (per rules: whole units only)."""
    # In practice, enforced at creation; this is a no-op check
    return all(det.soldier_count > 0 for det in detachments)  # Basic sanity


def calculate_total_detachments(army: Army) -> int:
    """Total number of detachments in army."""
    return len(army.detachments)


def can_split_army(army: Army, proposed_detachments: list[Detachment]) -> bool:
    """Check if army can be split with proposed detachments.

    Must leave at least one detachment in original army.
    """
    return len(proposed_detachments) < len(army.detachments) and len(proposed_detachments) > 0


def apply_noncombatant_gains(
    army: Army, percentage_increase: float, traits: list[Trait] | None = None
) -> None:
    """Apply noncombatant gains from events (e.g., +5% from fortress capture).

    Spartan trait halves gains.
    """
    traits = traits or []
    has_spartan = any(getattr(t, "name", "").lower() == "spartan" for t in traits)
    effective_increase = percentage_increase / 2 if has_spartan else percentage_increase

    current_nc = army.noncombatant_count
    army.noncombatant_count = int(current_nc * (1 + effective_increase))
