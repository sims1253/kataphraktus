"""Rules for detachments harrying opposing armies."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain.enums import ArmyStatus
from cataphract.domain.models import Army, Detachment, UnitType, UnitTypeID
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice


@dataclass(slots=True)
class HarryingOptions:
    """Configuration for a harrying attempt."""

    objective: str = "kill"
    rules: RulesConfig = DEFAULT_RULES


@dataclass(slots=True)
class HarryingResult:
    """Outcome returned when resolving a harrying attempt."""

    success: bool
    detail: str
    roll: int
    modifier: int
    inflicted_casualties: int = 0
    attacker_losses: int = 0
    supplies_burned: int = 0
    supplies_stolen: int = 0
    loot_stolen: int = 0


@dataclass(slots=True)
class HarryingResolutionContext:
    """Shared values for resolving harrying outcomes."""

    attacker: Army
    target: Army
    total_soldiers: int
    modifier: int
    roll: int
    seed: str


def _harrying_modifier(unit_types: dict[UnitTypeID, UnitType], detached: list[Detachment]) -> int:
    has_skirmisher = any(_has_ability(unit_types, det, "skirmisher") for det in detached)
    has_cavalry = any(_unit_category(unit_types, det) == "cavalry" for det in detached)
    return (1 if has_skirmisher else 0) + (2 if has_cavalry else 0)


def _mark_harrying_state(attacker: Army, target: Army, current_day: int, objective: str) -> None:
    attacker.status = ArmyStatus.HARRYING
    attacker.movement_points_remaining = 0.0

    target.status_effects = target.status_effects or {}
    target.status_effects["harried"] = {
        "day": current_day,
        "objective": objective,
        "penalty": 0.5,
    }
    target.movement_points_remaining = min(target.movement_points_remaining, 0.5)


def _resolve_harrying_success(
    context: HarryingResolutionContext,
    objective: str,
) -> HarryingResult:
    if objective == OBJECTIVE_KILL:
        casualties = max(1, (context.total_soldiers * 20) // 100)
        _apply_casualties(context.target, casualties)
        detail = f"harrying success: inflicted {casualties} casualties"
        return HarryingResult(
            True, detail, context.roll, context.modifier, inflicted_casualties=casualties
        )

    if objective == OBJECTIVE_TORCH:
        burn_roll = max(1, roll_dice(f"{context.seed}:torch", "2d6")["total"] + context.modifier)
        burned = context.total_soldiers * burn_roll
        supplies_removed = min(burned, context.target.supplies_current)
        context.target.supplies_current -= supplies_removed
        detail = f"harrying success: torched {supplies_removed} supplies"
        return HarryingResult(
            True, detail, context.roll, context.modifier, supplies_burned=supplies_removed
        )

    if objective == OBJECTIVE_STEAL:
        steal_roll = max(1, roll_dice(f"{context.seed}:steal", "1d6")["total"] + context.modifier)
        haul = context.total_soldiers * steal_roll
        loot_taken = min(haul, context.target.loot_carried)
        context.target.loot_carried -= loot_taken
        remaining = haul - loot_taken
        supplies_taken = 0
        if remaining > 0:
            capacity = max(
                0, context.attacker.supplies_capacity - context.attacker.supplies_current
            )
            supplies_taken = min(remaining, context.target.supplies_current, capacity)
            context.target.supplies_current -= supplies_taken
            context.attacker.supplies_current += supplies_taken
        context.attacker.loot_carried += loot_taken
        detail = f"harrying success: stole {loot_taken} loot"
        if supplies_taken:
            detail += f" and {supplies_taken} supplies"
        return HarryingResult(
            True,
            detail,
            context.roll,
            context.modifier,
            loot_stolen=loot_taken,
            supplies_stolen=supplies_taken,
        )

    raise ValueError(f"unknown harrying objective: {objective}")


def _resolve_harrying_failure(
    detached: list[Detachment],
    total_soldiers: int,
    modifier: int,
    roll: int,
) -> HarryingResult:
    losses = max(
        1, (total_soldiers * FAILURE_LOSS_RATIO_NUMERATOR) // FAILURE_LOSS_RATIO_DENOMINATOR
    )
    _apply_casualties_to_detachments(detached, losses)
    detail = f"harrying failed: detachment lost {losses} soldiers"
    return HarryingResult(False, detail, roll, modifier, attacker_losses=losses)


BASE_SUCCESS_THRESHOLD = 2
FAILURE_LOSS_RATIO_NUMERATOR = 1
FAILURE_LOSS_RATIO_DENOMINATOR = 5  # 20%


OBJECTIVE_KILL = "kill"
OBJECTIVE_TORCH = "torch"
OBJECTIVE_STEAL = "steal"


def resolve_harrying(
    campaign,
    attacker: Army,
    target: Army,
    detached: list[Detachment],
    *,
    options: HarryingOptions | None = None,
) -> HarryingResult:
    """Execute a harrying attempt from *attacker* towards *target*."""

    if not detached:
        raise ValueError("harrying requires at least one detachment")

    total_soldiers = sum(det.soldiers for det in detached)
    if total_soldiers <= 0:
        raise ValueError("harrying detachment has no soldiers")

    options = options or HarryingOptions()
    objective = options.objective.lower()
    modifier = _harrying_modifier(campaign.unit_types, detached)

    seed = f"harry:{int(attacker.id)}:{int(target.id)}:{campaign.current_day}"
    roll = roll_dice(seed, "1d6")["total"]
    success = roll <= min(6, BASE_SUCCESS_THRESHOLD + modifier)

    _mark_harrying_state(attacker, target, campaign.current_day, objective)

    context_values = HarryingResolutionContext(
        attacker=attacker,
        target=target,
        total_soldiers=total_soldiers,
        modifier=modifier,
        roll=roll,
        seed=seed,
    )

    if success:
        return _resolve_harrying_success(context_values, objective)

    return _resolve_harrying_failure(detached, total_soldiers, modifier, roll)


# ---------------------------------------------------------------------------
# Helpers


def _has_ability(unit_types: dict[UnitTypeID, UnitType], det: Detachment, ability: str) -> bool:
    unit = unit_types.get(det.unit_type_id)
    if unit is None or not unit.special_abilities:
        return False
    value = unit.special_abilities.get(ability)
    return bool(value)


def _unit_category(unit_types: dict[UnitTypeID, UnitType], det: Detachment) -> str:
    unit = unit_types.get(det.unit_type_id)
    return unit.category if unit else "infantry"


def _apply_casualties(target: Army, casualties: int) -> None:
    """Remove *casualties* soldiers from the defending army."""

    remaining = casualties
    for det in target.detachments:
        if remaining <= 0:
            break
        loss = min(det.soldiers, remaining)
        det.soldiers -= loss
        remaining -= loss
    if remaining > 0:
        target.noncombatant_count = max(0, target.noncombatant_count - remaining)


def _apply_casualties_to_detachments(detachments: list[Detachment], losses: int) -> None:
    remaining = losses
    for det in detachments:
        if remaining <= 0:
            break
        loss = min(det.soldiers, remaining)
        det.soldiers -= loss
        remaining -= loss
