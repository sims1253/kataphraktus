"""Siege progression rules."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain.enums import SiegeStatus
from cataphract.domain.models import Siege
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice


@dataclass(slots=True)
class SiegeAdvanceResult:
    """Summary of a weekly siege advance."""

    gates_opened: bool
    threshold_after: int
    roll: int


def advance_siege(
    siege: Siege,
    *,
    roll_seed: str = "siege-threshold",
    rules: RulesConfig = DEFAULT_RULES,
) -> SiegeAdvanceResult:
    """Advance a siege by one week, mutating the siege record."""

    siege.weeks_elapsed += 1
    threshold = siege.current_threshold
    threshold += rules.siege.default_modifier

    for modifier in siege.threshold_modifiers:
        kind = modifier.get("type")
        value = modifier.get("value")
        if isinstance(value, (int, float)):
            threshold += int(value)
        elif kind == "disease":
            threshold += rules.siege.disease_modifier
        elif kind == "resupply":
            threshold += rules.siege.resupply_modifier
        elif kind == "attacked":
            threshold += rules.siege.attacked_modifier

    if siege.siege_engines_count:
        threshold -= siege.siege_engines_count * rules.siege.siege_engine_reduction_per_detachment

    siege.current_threshold = max(rules.siege.starvation_threshold, threshold)

    roll = roll_dice(roll_seed, "2d6")["total"]
    gates_opened = roll > siege.current_threshold
    if gates_opened:
        siege.status = SiegeStatus.GATES_OPENED

    return SiegeAdvanceResult(
        gates_opened=gates_opened,
        threshold_after=siege.current_threshold,
        roll=roll,
    )
