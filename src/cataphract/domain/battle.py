"""Battle resolution rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from cataphract.domain import morale
from cataphract.domain.enums import ArmyStatus
from cataphract.domain.models import Army, ArmyID, CommanderID, UnitType, UnitTypeID
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice

MAJOR_CAPTURE_DIFF = 6
MINOR_CAPTURE_DIFF = 4
MAJOR_CASUALTY_DIFF = 6
SIGNIFICANT_CASUALTY_DIFF = 4
MODERATE_CASUALTY_DIFF = 2


@dataclass(slots=True)
class BattleOptions:
    """Configuration for resolving a battle."""

    attacker_modifier: int = 0
    defender_modifier: int = 0
    attacker_modifiers: dict[ArmyID, int] | None = None
    defender_modifiers: dict[ArmyID, int] | None = None
    attacker_fixed_rolls: dict[ArmyID, int] | None = None
    defender_fixed_rolls: dict[ArmyID, int] | None = None
    attacker_seed: str = "attacker-battle"
    defender_seed: str = "defender-battle"


@dataclass(slots=True)
class SideContext:
    """Cached data for a side participating in the battle."""

    strength: float
    seed: str
    fixed_rolls: dict[ArmyID, int] | None
    modifiers: dict[ArmyID, int] | None
    side_modifier: int


@dataclass(slots=True)
class ArmyBattleRecord:
    """Rolls and casualties for a single army."""

    roll: int
    modifiers: dict[str, int] = field(default_factory=dict)
    casualty_pct: float = 0.0
    morale_delta: int = 0
    routed: bool = False
    retreat_hexes: int | None = None
    commander_captured: bool = False


@dataclass(slots=True)
class BattleResult:
    """Summary of a resolved battle."""

    winner: str
    attacker_records: dict[ArmyID, ArmyBattleRecord]
    defender_records: dict[ArmyID, ArmyBattleRecord]
    roll_difference: int
    captured_commanders: list[CommanderID]
    notes: list[str] = field(default_factory=list)


def resolve_battle(
    attackers: Army | Sequence[Army],
    defenders: Army | Sequence[Army],
    *,
    unit_types: dict[UnitTypeID, UnitType] | None = None,
    options: BattleOptions | None = None,
    rules: RulesConfig = DEFAULT_RULES,
) -> BattleResult:
    """Resolve a battle between one or more armies."""

    options = options or BattleOptions()
    attacker_list = _normalize_armies(attackers)
    defender_list = _normalize_armies(defenders)

    total_attacker_strength = (
        sum(_effective_strength(army, unit_types) for army in attacker_list) or 1
    )
    total_defender_strength = (
        sum(_effective_strength(army, unit_types) for army in defender_list) or 1
    )

    attacker_context = SideContext(
        strength=total_attacker_strength,
        seed=options.attacker_seed,
        fixed_rolls=options.attacker_fixed_rolls,
        modifiers=options.attacker_modifiers,
        side_modifier=options.attacker_modifier,
    )
    defender_context = SideContext(
        strength=total_defender_strength,
        seed=options.defender_seed,
        fixed_rolls=options.defender_fixed_rolls,
        modifiers=options.defender_modifiers,
        side_modifier=options.defender_modifier,
    )

    attacker_rolls = _build_side_records(
        attacker_list, attacker_context, total_defender_strength, rules
    )
    defender_rolls = _build_side_records(
        defender_list, defender_context, total_attacker_strength, rules
    )

    (
        winner,
        losing_records,
        losing_armies,
        roll_difference,
        attacker_best_roll,
        defender_best_roll,
    ) = _determine_winner(attacker_rolls, defender_rolls, attacker_list, defender_list)

    captured_commanders: list[CommanderID] = []
    notes: list[str] = []

    # Apply casualties and morale shifts per army
    for army in attacker_list:
        record = attacker_rolls[army.id]
        enemy_max = defender_best_roll
        _apply_battle_resolution(
            army,
            record,
            record.roll - (enemy_max if enemy_max else 0),
            winning=(winner == "attacker"),
            rules=rules,
        )
        if record.commander_captured:
            commander_id = army.commander_id
            captured_commanders.append(commander_id)

    for army in defender_list:
        record = defender_rolls[army.id]
        enemy_max = attacker_best_roll
        _apply_battle_resolution(
            army,
            record,
            record.roll - enemy_max,
            winning=(winner == "defender"),
            rules=rules,
        )
        if record.commander_captured:
            commander_id = army.commander_id
            captured_commanders.append(commander_id)

    # Apply retreat consequences to the losing side
    for army in losing_armies:
        record = losing_records.get(army.id)
        if record is None:
            continue
        _apply_retreat_if_needed(
            army,
            record,
            roll_difference,
            rules,
        )

    return BattleResult(
        winner=winner,
        attacker_records=attacker_rolls,
        defender_records=defender_rolls,
        roll_difference=roll_difference,
        captured_commanders=captured_commanders,
        notes=notes,
    )


def _normalize_armies(armies: Army | Sequence[Army]) -> list[Army]:
    if isinstance(armies, Army):
        return [armies]
    return list(armies)


def _build_side_records(
    armies: Sequence[Army],
    context: SideContext,
    enemy_strength: float,
    rules: RulesConfig,
) -> dict[ArmyID, ArmyBattleRecord]:
    records: dict[ArmyID, ArmyBattleRecord] = {}
    for army in armies:
        records[army.id] = _roll_for_army(army, context, enemy_strength, rules)
    return records


def _determine_winner(
    attacker_rolls: dict[ArmyID, ArmyBattleRecord],
    defender_rolls: dict[ArmyID, ArmyBattleRecord],
    attacker_list: Sequence[Army],
    defender_list: Sequence[Army],
) -> tuple[str, dict[ArmyID, ArmyBattleRecord], Sequence[Army], int, int, int]:
    best_attacker = max(attacker_rolls.values(), key=lambda rec: rec.roll, default=None)
    best_defender = max(defender_rolls.values(), key=lambda rec: rec.roll, default=None)

    attacker_best_roll = best_attacker.roll if best_attacker else 0
    defender_best_roll = best_defender.roll if best_defender else 0
    raw_difference = attacker_best_roll - defender_best_roll

    if raw_difference > 0:
        return (
            "attacker",
            defender_rolls,
            defender_list,
            raw_difference,
            attacker_best_roll,
            defender_best_roll,
        )
    if raw_difference < 0:
        return (
            "defender",
            attacker_rolls,
            attacker_list,
            abs(raw_difference),
            attacker_best_roll,
            defender_best_roll,
        )
    return "defender", attacker_rolls, attacker_list, 0, attacker_best_roll, defender_best_roll


def _effective_strength(army: Army, unit_types: dict[UnitTypeID, UnitType] | None) -> float:
    strength = 0.0
    for det in army.detachments:
        unit = unit_types.get(det.unit_type_id) if unit_types else None
        multiplier = getattr(unit, "battle_multiplier", 1.0) if unit else 1.0
        strength += det.soldiers * multiplier
    return max(1.0, strength)


def _roll_for_army(
    army: Army,
    context: SideContext,
    enemy_strength: float,
    rules: RulesConfig,
) -> ArmyBattleRecord:
    fixed = (context.fixed_rolls or {}).get(army.id)
    if fixed is not None:
        base_roll = fixed
    else:
        base_roll = roll_dice(f"{context.seed}:{int(army.id)}", "2d6")["total"]

    modifiers: dict[str, int] = {}
    numeric_bonus = _numeric_advantage(context.strength, enemy_strength, rules)
    if numeric_bonus:
        modifiers["numeric"] = numeric_bonus

    morale_bonus = max(-2, min(2, (army.morale_current - army.morale_resting) // 2))
    if morale_bonus:
        modifiers["morale"] = morale_bonus

    sickness_penalty = -1 if (army.status_effects or {}).get("sick_or_exhausted") else 0
    if sickness_penalty:
        modifiers["exhaustion"] = sickness_penalty

    per_army = (context.modifiers or {}).get(army.id, 0)
    if per_army:
        modifiers["order"] = per_army

    if context.side_modifier:
        modifiers["side"] = modifiers.get("side", 0) + context.side_modifier

    total_modifier = sum(modifiers.values())
    roll_total = base_roll + total_modifier

    return ArmyBattleRecord(roll=roll_total, modifiers=modifiers)


def _numeric_advantage(own_strength: float, enemy_strength: float, rules: RulesConfig) -> int:
    if enemy_strength <= 0:
        return 3
    ratio = own_strength / enemy_strength
    if ratio <= 1:
        return 0
    advantage = ratio - 1
    return int(advantage / rules.battle.multi_side_numeric_bonus_ratio)


def _apply_battle_resolution(
    army: Army,
    record: ArmyBattleRecord,
    roll_difference: int,
    *,
    winning: bool,
    rules: RulesConfig,
) -> None:
    diff_magnitude = abs(roll_difference)
    casualty_attacker, casualty_defender, morale_adjustments = _lookup_casualties(diff_magnitude)
    casualty = casualty_attacker if winning else casualty_defender
    record.casualty_pct = casualty

    for det in army.detachments:
        det.soldiers = max(1, int(det.soldiers * (1 - casualty)))
    army.supplies_current = int(army.supplies_current * (1 - casualty))

    morale_delta = morale_adjustments["attacker"] if winning else morale_adjustments["defender"]
    record.morale_delta = morale_delta
    morale.adjust_morale(army, morale_delta, max_morale=army.morale_max)

    if army.morale_current <= rules.battle.rout_threshold:
        army.status = ArmyStatus.ROUTED
        record.routed = True

    # Commander capture chance when losing badly
    if not winning and roll_difference <= -MAJOR_CAPTURE_DIFF:
        capture_target = rules.battle.capture_chance_major
    elif not winning and roll_difference <= -MINOR_CAPTURE_DIFF:
        capture_target = rules.battle.capture_chance_minor
    else:
        capture_target = 0

    if capture_target:
        roll = roll_dice(f"commander-capture:{int(army.id)}", "1d6")["total"]
        if roll <= capture_target:
            record.commander_captured = True


def _apply_retreat_if_needed(
    army: Army,
    record: ArmyBattleRecord,
    roll_difference: int,
    rules: RulesConfig,
) -> None:
    if record.routed:
        retreat_roll = roll_dice(f"retreat:{int(army.id)}", f"1d{rules.battle.retreat_hexes_max}")[
            "total"
        ]
        retreat_hexes = max(
            rules.battle.retreat_hexes_min,
            min(rules.battle.retreat_hexes_max, retreat_roll),
        )
        record.retreat_hexes = retreat_hexes
        loss_die = roll_dice(
            f"retreat-supplies:{int(army.id)}", f"1d{rules.battle.retreat_supply_loss_die}"
        )["total"]
        loss_percent = loss_die * rules.battle.retreat_supply_loss_multiplier / 100
        army.supplies_current = int(army.supplies_current * (1 - loss_percent))
        return

    if roll_difference <= 0:
        return

    # Losing side fallback even if not routed
    retreat_die = roll_dice(f"fallback:{int(army.id)}", "1d2")["total"]
    if retreat_die == 1:
        record.retreat_hexes = rules.battle.retreat_hexes_min


def _lookup_casualties(diff: int) -> tuple[float, float, dict[str, int]]:
    if diff >= MAJOR_CASUALTY_DIFF:
        return 0.05, 0.20, {"attacker": +2, "defender": -2}
    if diff >= SIGNIFICANT_CASUALTY_DIFF:
        return 0.05, 0.15, {"attacker": +2, "defender": -2}
    if diff >= MODERATE_CASUALTY_DIFF:
        return 0.05, 0.10, {"attacker": +1, "defender": -2}
    if diff >= 1:
        return 0.10, 0.10, {"attacker": 0, "defender": -1}
    return 0.05, 0.05, {"attacker": -1, "defender": 0}
