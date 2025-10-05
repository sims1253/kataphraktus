"""Tests for daily tick orchestration."""

from __future__ import annotations

from datetime import date

from cataphract.domain import models as dm
from cataphract.domain import tick
from cataphract.domain.enums import ArmyStatus, DayPart, Season


def _campaign() -> dm.Campaign:
    return dm.Campaign(
        id=dm.CampaignID(1),
        name="Test",
        start_date=date(1325, 3, 1),
        current_day=0,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )


def _army(campaign: dm.Campaign) -> dm.Army:
    det = dm.Detachment(
        id=dm.DetachmentID(1),
        unit_type_id=dm.UnitTypeID(1),
        soldiers=500,
        wagons=0,
    )
    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(1),
        current_hex_id=dm.HexID(1),
        detachments=[det],
        status=ArmyStatus.IDLE,
        supplies_current=1_000,
        noncombatant_count=100,
        status_effects={},
    )
    campaign.armies[army.id] = army
    return army


def test_tick_consumes_supplies_and_advances_day():
    campaign = _campaign()
    army = _army(campaign)
    tick.run_daily_tick(campaign)
    assert campaign.current_day == 1
    assert army.supplies_current < 1_000
