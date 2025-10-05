"""Unit tests for battle resolution."""

from __future__ import annotations

from cataphract.domain import battle
from cataphract.domain import models as dm


def _unit_types() -> dict[dm.UnitTypeID, dm.UnitType]:
    return {
        dm.UnitTypeID(1): dm.UnitType(
            id=dm.UnitTypeID(1),
            name="infantry",
            category="infantry",
            battle_multiplier=1.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
        ),
        dm.UnitTypeID(2): dm.UnitType(
            id=dm.UnitTypeID(2),
            name="heavy_cavalry",
            category="cavalry",
            battle_multiplier=2.0,
            supply_cost_per_day=10,
            can_travel_offroad=True,
        ),
    }


def _army(name: str, *, unit_type_id: int = 1) -> dm.Army:
    detachments = [
        dm.Detachment(
            id=dm.DetachmentID(1 if name == "attacker" else 2),
            unit_type_id=dm.UnitTypeID(unit_type_id),
            soldiers=500,
            wagons=0,
        )
    ]
    return dm.Army(
        id=dm.ArmyID(1 if name == "attacker" else 2),
        campaign_id=dm.CampaignID(1),
        commander_id=dm.CommanderID(1 if name == "attacker" else 2),
        current_hex_id=dm.HexID(1),
        detachments=detachments,
        status=dm.ArmyStatus.IDLE,
        morale_current=9,
        morale_resting=9,
        morale_max=12,
        supplies_current=10_000,
        noncombatant_count=100,
        status_effects={},
    )


def test_attacker_victory():
    attacker = _army("attacker")
    defender = _army("defender")
    options = battle.BattleOptions(
        attacker_fixed_rolls={attacker.id: 10},
        defender_fixed_rolls={defender.id: 4},
    )
    result = battle.resolve_battle(
        attacker,
        defender,
        unit_types=_unit_types(),
        options=options,
    )
    assert result.winner == "attacker"
    attacker_record = result.attacker_records[attacker.id]
    defender_record = result.defender_records[defender.id]
    assert attacker_record.casualty_pct == 0.05
    assert defender_record.casualty_pct == 0.20
    assert attacker.morale_current >= 9
    assert defender.morale_current < 9


def test_defender_holds_on_tie():
    attacker = _army("attacker")
    defender = _army("defender")
    options = battle.BattleOptions(
        attacker_fixed_rolls={attacker.id: 7},
        defender_fixed_rolls={defender.id: 7},
    )
    result = battle.resolve_battle(
        attacker,
        defender,
        unit_types=_unit_types(),
        options=options,
    )
    assert result.winner == "defender"
    assert result.attacker_records[attacker.id].casualty_pct == 0.05
    assert result.defender_records[defender.id].casualty_pct == 0.05


def test_multi_army_numeric_advantage():
    attacker_primary = _army("attacker", unit_type_id=2)
    attacker_support = _army("attacker", unit_type_id=2)
    attacker_support.id = dm.ArmyID(3)
    attacker_support.commander_id = dm.CommanderID(3)

    defender = _army("defender")
    options = battle.BattleOptions(
        attacker_fixed_rolls={attacker_primary.id: 8, attacker_support.id: 7},
        defender_fixed_rolls={defender.id: 5},
    )
    result = battle.resolve_battle(
        [attacker_primary, attacker_support],
        defender,
        unit_types=_unit_types(),
        options=options,
    )

    assert result.winner == "attacker"
    defender_record = result.defender_records[defender.id]
    assert defender_record.casualty_pct >= 0.15
