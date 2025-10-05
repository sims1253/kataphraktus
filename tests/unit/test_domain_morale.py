"""Unit tests for morale rules."""

from __future__ import annotations

from cataphract.domain import models as dm
from cataphract.domain import morale
from cataphract.domain.enums import ArmyStatus


def _army() -> dm.Army:
    detachments = [
        dm.Detachment(
            id=dm.DetachmentID(1),
            unit_type_id=dm.UnitTypeID(1),
            soldiers=500,
            wagons=0,
        ),
        dm.Detachment(
            id=dm.DetachmentID(2),
            unit_type_id=dm.UnitTypeID(1),
            soldiers=400,
            wagons=0,
        ),
    ]
    return dm.Army(
        id=dm.ArmyID(1),
        campaign_id=dm.CampaignID(1),
        commander_id=dm.CommanderID(1),
        current_hex_id=dm.HexID(1),
        detachments=detachments,
        status=ArmyStatus.IDLE,
        morale_current=9,
        morale_resting=9,
        morale_max=12,
        supplies_current=10_000,
        noncombatant_count=200,
        status_effects={},
    )


def _trait(name: str) -> dm.Trait:
    return dm.Trait(id=1, name=name, description=name, scope_tags=[], effect_data={})


def test_roll_morale_check_success():
    success, roll = morale.roll_morale_check(9, "seed")
    assert isinstance(success, bool)
    assert 2 <= roll <= 12


def test_mass_desertion_reduces_strength():
    army = _army()
    before = sum(det.soldiers for det in army.detachments)
    morale.apply_morale_consequence(
        army,
        roll=3,
        traits=[],
        seed="mass-desertion",
    )
    after = sum(det.soldiers for det in army.detachments)
    assert after < before


def test_camp_followers_increases_noncombatants():
    army = _army()
    before = army.noncombatant_count
    morale.apply_morale_consequence(
        army,
        roll=10,
        traits=[],
        seed="camp-followers",
    )
    assert army.noncombatant_count > before


def test_departing_detachments_set_status_effect():
    army = _army()
    result = morale.apply_morale_consequence(
        army,
        roll=9,
        traits=[_trait("poet")],
        seed="depart",
        current_day=20,
    )
    if army.status_effects:
        assert "departed_detachments" in army.status_effects
        data = army.status_effects["departed_detachments"]
        assert data["return_day"] > 20
    assert "departing_detachments" in result
