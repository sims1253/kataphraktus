"""Morale rules for Cataphract armies."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import Enum

from cataphract.domain.models import Army, Trait
from cataphract.utils.rng import check_success, random_choice, roll_dice


class MoraleConsequence(Enum):
    MUTINY = 2
    MASS_DESERTION = 3
    DETACHMENTS_DEFECT = 4
    MAJOR_DESERTION = 5
    ARMY_SPLITS = 6
    RANDOM_DETACHMENT_DEFECTS = 7
    DESERTION = 8
    DETACHMENTS_DEPART = 9
    CAMP_FOLLOWERS = 10
    DETACHMENT_DEPARTS = 11
    NO_CONSEQUENCES = 12


def roll_morale_check(morale: int, seed: str) -> tuple[bool, int]:
    """Roll 2d6 morale check: success if <= morale."""

    result = roll_dice(seed, "2d6")
    total = result["total"]
    return total <= morale, total


def adjust_morale(army: Army, change: int, *, max_morale: int = 12) -> None:
    """Adjust an army's morale within the provided bounds."""

    army.morale_current = max(2, min(max_morale, army.morale_current + change))


Handler = Callable[[Army, list[Trait], str, int], dict[str, object]]


def apply_morale_consequence(
    army: Army,
    roll: int,
    traits: Iterable[Trait],
    *,
    seed: str,
    current_day: int = 0,
) -> dict[str, object]:
    """Apply morale failure consequences to an army."""

    traits = list(traits)
    has_poet = any(getattr(t, "name", "").lower() == "poet" for t in traits)
    effective_roll = max(2, min(12, roll + (2 if has_poet else 0)))
    consequence = MoraleConsequence(effective_roll)
    details: dict[str, object] = {"consequence_type": consequence.name, "roll": roll}

    handler = _MORALE_HANDLERS.get(consequence)
    if handler is not None:
        details.update(handler(army, traits, seed, current_day))
    return details


def _apply_percentage_loss(army: Army, percentage: float) -> None:
    for det in army.detachments:
        remaining = max(1, int(det.soldiers * (1 - percentage)))
        det.soldiers = remaining
    army.supplies_current = int(army.supplies_current * (1 - percentage))


def _select_detachments(army: Army, count: int, seed: str) -> list:
    if count <= 0 or not army.detachments:
        return []
    indices = list(range(len(army.detachments)))
    selected = []
    for i in range(min(count, len(indices))):
        choice = random_choice(f"{seed}:select:{i}", indices)
        idx = choice["index"]
        selected.append(army.detachments[idx])
        indices.remove(idx)
    return selected


def _handle_mutiny(army: Army, _traits: list[Trait], seed: str, _day: int) -> dict[str, object]:
    losses = []
    for index, det in enumerate(army.detachments):
        chance = check_success(f"{seed}:mutiny:{index}", 19 / 20, "1d20")
        if chance["success"]:
            losses.append(det)
    return {"defecting_detachments": len(losses)}


def _handle_mass_desertion(
    army: Army, _traits: list[Trait], _seed: str, _day: int
) -> dict[str, object]:
    _apply_percentage_loss(army, 0.30)
    return {"loss_percentage": 0.30}


def _handle_detachments_defect(
    army: Army, _traits: list[Trait], seed: str, _day: int
) -> dict[str, object]:
    num = roll_dice(f"{seed}:defect-count", "1d6")["total"]
    num = min(num, max(0, len(army.detachments) - 1))
    selected = _select_detachments(army, num, seed)
    return {"defecting_detachments": len(selected)}


def _handle_major_desertion(
    army: Army, _traits: list[Trait], _seed: str, _day: int
) -> dict[str, object]:
    _apply_percentage_loss(army, 0.20)
    return {"loss_percentage": 0.20}


def _handle_army_splits(
    army: Army, _traits: list[Trait], seed: str, _day: int
) -> dict[str, object]:
    splitting = []
    for index, det in enumerate(army.detachments):
        chance = check_success(f"{seed}:split:{index}", 0.5, "1d6")
        if chance["success"]:
            splitting.append(det)
    if len(splitting) >= len(army.detachments):
        splitting = splitting[:-1]
    return {"splitting_detachments": len(splitting)}


def _handle_random_defect(
    army: Army, _traits: list[Trait], seed: str, _day: int
) -> dict[str, object]:
    selected = _select_detachments(army, 1, seed)
    return {"defecting_detachments": len(selected)}


def _handle_desertion(army: Army, _traits: list[Trait], _seed: str, _day: int) -> dict[str, object]:
    _apply_percentage_loss(army, 0.10)
    return {"loss_percentage": 0.10}


def _handle_detachments_depart(
    army: Army, _traits: list[Trait], seed: str, current_day: int
) -> dict[str, object]:
    num = roll_dice(f"{seed}:depart-count", "1d6")["total"]
    days = roll_dice(f"{seed}:depart-days", "2d6")["total"]
    num = min(num, max(0, len(army.detachments) - 1))
    selected = _select_detachments(army, num, seed)
    if selected:
        army.status_effects = army.status_effects or {}
        army.status_effects["departed_detachments"] = {
            "detachment_ids": [det.id for det in selected],
            "return_day": current_day + days,
        }
    return {"departing_detachments": len(selected), "return_in_days": days}


def _handle_camp_followers(
    army: Army, _traits: list[Trait], _seed: str, _day: int
) -> dict[str, object]:
    increase = int(army.noncombatant_count * 0.05)
    army.noncombatant_count += increase
    return {"noncombatant_increase": increase}


def _handle_detachment_departs(
    army: Army, _traits: list[Trait], seed: str, current_day: int
) -> dict[str, object]:
    selected = _select_detachments(army, 1, seed)
    if not selected:
        return {"departing_detachments": 0}
    days = roll_dice(f"{seed}:single-depart-days", "2d6")["total"]
    army.status_effects = army.status_effects or {}
    army.status_effects["departed_detachments"] = {
        "detachment_ids": [selected[0].id],
        "return_day": current_day + days,
    }
    return {"departing_detachments": 1, "return_in_days": days}


_MORALE_HANDLERS: dict[MoraleConsequence, Handler] = {
    MoraleConsequence.MUTINY: _handle_mutiny,
    MoraleConsequence.MASS_DESERTION: _handle_mass_desertion,
    MoraleConsequence.DETACHMENTS_DEFECT: _handle_detachments_defect,
    MoraleConsequence.MAJOR_DESERTION: _handle_major_desertion,
    MoraleConsequence.ARMY_SPLITS: _handle_army_splits,
    MoraleConsequence.RANDOM_DETACHMENT_DEFECTS: _handle_random_defect,
    MoraleConsequence.DESERTION: _handle_desertion,
    MoraleConsequence.DETACHMENTS_DEPART: _handle_detachments_depart,
    MoraleConsequence.CAMP_FOLLOWERS: _handle_camp_followers,
    MoraleConsequence.DETACHMENT_DEPARTS: _handle_detachment_departs,
}
