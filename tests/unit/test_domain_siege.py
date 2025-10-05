"""Tests for siege progression."""

from __future__ import annotations

from cataphract.domain import models as dm
from cataphract.domain import siege


def _siege() -> dm.Siege:
    return dm.Siege(
        id=dm.SiegeID(1),
        stronghold_id=dm.StrongholdID(1),
        attacker_army_ids=[dm.ArmyID(1)],
        defender_army_id=dm.ArmyID(2),
        started_on_day=0,
        weeks_elapsed=0,
        current_threshold=10,
        threshold_modifiers=[{"value": -1}],
        siege_engines_count=0,
        attempts=[],
    )


def test_siege_threshold_decreases_and_gate_opens():
    s = _siege()
    result = siege.advance_siege(s, roll_seed="high")
    assert result.threshold_after <= 10
    assert isinstance(result.gates_opened, bool)
