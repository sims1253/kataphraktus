"""Tests for the JSON campaign repository."""

from __future__ import annotations

from datetime import date

from cataphract.domain import models as dm
from cataphract.domain.enums import DayPart, Season
from cataphract.repository import JsonCampaignRepository


def _campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Test",
        start_date=date(1325, 3, 1),
        current_day=5,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )

    hex_ = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=40,
        controlling_faction_id=None,
    )
    campaign.map.hexes[hex_.id] = hex_
    return campaign


def test_save_and_load_campaign(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    campaign = _campaign()

    path = repo.save(campaign)
    assert path.exists()

    loaded = repo.load(dm.CampaignID(1))
    assert loaded == campaign


def test_list_and_delete(tmp_path):
    repo = JsonCampaignRepository(tmp_path)
    first = _campaign()
    second = _campaign()
    second.id = dm.CampaignID(2)

    repo.save(first)
    repo.save(second)

    ids = repo.list_campaigns()
    assert ids == [dm.CampaignID(1), dm.CampaignID(2)]

    repo.delete(dm.CampaignID(1))
    assert repo.list_campaigns() == [dm.CampaignID(2)]
