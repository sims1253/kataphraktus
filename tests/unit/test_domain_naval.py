"""Unit tests for naval transport rules."""

from __future__ import annotations

from datetime import date

from cataphract.domain import models as dm
from cataphract.domain import naval
from cataphract.domain.enums import ArmyStatus, DayPart, NavalStatus, Season


def _campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Sea Trial",
        start_date=date(1325, 3, 1),
        current_day=0,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )
    origin = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="coast",
        settlement=40,
    )
    destination = dm.Hex(
        id=dm.HexID(2),
        campaign_id=campaign.id,
        q=1,
        r=0,
        terrain="coast",
        settlement=40,
    )
    campaign.map.hexes[origin.id] = origin
    campaign.map.hexes[destination.id] = destination
    return campaign


def test_embark_sail_and_disembark():
    campaign = _campaign()
    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(1),
        current_hex_id=dm.HexID(1),
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(1),
                unit_type_id=dm.UnitTypeID(1),
                soldiers=500,
            )
        ],
        status=ArmyStatus.IDLE,
        status_effects={},
    )
    campaign.armies[army.id] = army

    ship = dm.Ship(
        id=dm.ShipID(1),
        campaign_id=campaign.id,
        controlling_faction_id=dm.FactionID(1),
        current_hex_id=dm.HexID(1),
        ship_type_id=dm.ShipTypeID(1),
        status=NavalStatus.AVAILABLE,
    )
    campaign.ships[ship.id] = ship

    embark = naval.embark_army(campaign, army, ship)
    assert embark.success
    assert ship.status == NavalStatus.TRANSPORTING
    assert army.embarked_ship_id == ship.id

    result = naval.set_course(campaign, ship, [dm.HexID(2)])
    assert result.success
    assert ship.travel_days_remaining > 0

    # Advance the ship to its destination
    naval.advance_ships(campaign, day_fraction=1.0)
    assert ship.current_hex_id == dm.HexID(2)
    assert army.current_hex_id == dm.HexID(2)

    disembark = naval.disembark_army(campaign, army, ship)
    assert disembark.success
    assert ship.status == NavalStatus.AVAILABLE
    assert army.embarked_ship_id is None
