"""Tests for API runtime helpers (campaign service and tick manager)."""

from __future__ import annotations

from datetime import date

import pytest

from cataphract.api.runtime import CampaignService, OrderDraft, TickManager
from cataphract.domain import models as dm
from cataphract.domain.enums import ArmyStatus, DayPart, OrderStatus, Season
from cataphract.repository import JsonCampaignRepository


def _campaign(campaign_id: int = 1) -> dm.Campaign:
    return dm.Campaign(
        id=dm.CampaignID(campaign_id),
        name=f"Campaign {campaign_id}",
        start_date=date(1325, 3, 1),
        current_day=0,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )


def test_campaign_service_create_and_list(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    service = CampaignService(repo)

    campaign_a = service.create_campaign(name="Alpha", start_date=date(1325, 1, 1))
    campaign_b = service.create_campaign(name="Beta", start_date=date(1325, 1, 2))

    campaigns = service.list_campaigns()
    assert [c.name for c in campaigns] == ["Alpha", "Beta"]

    summary = service.to_summary_dict(campaign_a)
    assert summary["id"] == int(campaign_a.id)
    assert summary["pending_orders"] == 0

    detail = service.to_detail_dict(campaign_b)
    assert detail["armies"] == {}
    assert detail["orders"] == {}
    assert detail["commanders"] == {}


@pytest.mark.asyncio
async def test_tick_manager_advances_campaign(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    campaign = _campaign()
    repo.save(campaign)

    manager = TickManager(repo, base_interval_seconds=1.0)
    await manager.advance_now(campaign.id, days=2)

    updated = repo.load(campaign.id)
    assert updated.current_day == 2


@pytest.mark.asyncio
async def test_tick_manager_schedule_toggle(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    campaign = _campaign()
    repo.save(campaign)

    manager = TickManager(repo, base_interval_seconds=2.0)

    await manager.set_enabled(campaign.id, True)
    assert manager.is_enabled(campaign.id)
    assert campaign.id in manager.enabled_campaigns()

    manager.set_base_interval(10.0)
    manager.set_debug_multiplier(0.5)
    assert manager.base_interval_seconds == 10.0
    assert manager.debug_multiplier == 0.5
    assert manager.interval_seconds == pytest.approx(5.0)

    await manager.set_enabled(campaign.id, False)
    assert not manager.is_enabled(campaign.id)

    await manager.stop()


@pytest.mark.asyncio
async def test_campaign_service_create_and_cancel_order(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    campaign = _campaign()

    commander = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="Commander",
        faction_id=dm.FactionID(1),
        age=35,
    )

    hex_tile = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=10,
    )
    campaign.map.hexes[hex_tile.id] = hex_tile

    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=commander.id,
        current_hex_id=hex_tile.id,
        detachments=[],
        status=ArmyStatus.IDLE,
    )

    campaign.commanders[commander.id] = commander
    campaign.armies[army.id] = army
    repo.save(campaign)

    service = CampaignService(repo)

    order = service.create_order(
        campaign.id,
        OrderDraft(
            army_id=army.id,
            commander_id=commander.id,
            order_type="rest",
            parameters={"duration": 1},
            execute_part=DayPart.MORNING,
            priority=1,
        ),
    )

    stored = repo.load(campaign.id)
    assert order.id in stored.orders
    assert stored.armies[army.id].orders_queue == [order.id]

    cancelled = service.cancel_order(campaign.id, order.id)
    assert cancelled.status == OrderStatus.CANCELLED
    refreshed = repo.load(campaign.id)
    assert refreshed.armies[army.id].orders_queue == []
