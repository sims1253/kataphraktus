"""Special operation resolution rules."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain.enums import OperationOutcome
from cataphract.domain.models import Campaign, Operation
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice


@dataclass(slots=True)
class OperationResult:
    """Outcome data for an espionage operation."""

    success: bool
    roll: int
    target: int
    detail: str


def resolve_operation(
    campaign: Campaign,
    operation: Operation,
    *,
    rules: RulesConfig = DEFAULT_RULES,
    seed: str | None = None,
) -> OperationResult:
    """Resolve an operation immediately and mutate the record."""

    base_target = rules.operations.base_success_target
    modifier = operation.difficulty_modifier

    complexity = operation.complexity.lower()
    if complexity == "simple":
        modifier += rules.operations.simple_modifier
    elif complexity == "complex":
        modifier += rules.operations.complex_modifier

    territory = (operation.territory_type or "friendly").lower()
    if territory == "hostile":
        modifier += rules.operations.hostile_territory_modifier

    target = max(2, min(12, base_target - modifier))
    seed_value = seed or f"operation:{int(operation.id)}"
    roll = roll_dice(seed_value, "2d6")["total"]
    success = roll >= target

    operation.executed_on_day = campaign.current_day
    operation.success_chance = target
    operation.outcome = OperationOutcome.SUCCESS if success else OperationOutcome.FAILURE
    operation.result = {
        "roll": roll,
        "target": target,
        "success": success,
    }

    detail = "operation success" if success else "operation failed"
    return OperationResult(success=success, roll=roll, target=target, detail=detail)
