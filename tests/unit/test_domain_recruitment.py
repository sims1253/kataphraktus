"""Tests for the recruitment subsystem."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from cataphract.domain import models as dm
from cataphract.domain import orders
from cataphract.domain.enums import DayPart, OrderStatus, Season, StrongholdType
from cataphract.domain.rules_config import DEFAULT_RULES, RecruitmentRules


def _timestamp(day: int) -> datetime:
    return datetime(2025, 1, day, tzinfo=UTC)


def _campaign_with_stronghold() -> tuple[dm.Campaign, dm.Stronghold, dm.Commander, dm.Commander]:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Recruitment Test",
        start_date=date(1325, 3, 1),
        current_day=0,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )

    home_hex = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=120,
        controlling_faction_id=dm.FactionID(1),
        is_good_country=True,
    )
    campaign.map.hexes[home_hex.id] = home_hex

    unit_inf = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="infantry",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
    )
    unit_cav = dm.UnitType(
        id=dm.UnitTypeID(2),
        name="cavalry",
        category="cavalry",
        battle_multiplier=2.0,
        supply_cost_per_day=10,
        can_travel_offroad=True,
    )
    campaign.unit_types[unit_inf.id] = unit_inf
    campaign.unit_types[unit_cav.id] = unit_cav

    faction = dm.Faction(
        id=dm.FactionID(1),
        campaign_id=campaign.id,
        name="Hegemony",
        color="#123456",
    )
    campaign.factions[faction.id] = faction

    commander = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="Strategos",
        faction_id=faction.id,
        age=42,
    )
    subordinate = dm.Commander(
        id=dm.CommanderID(2),
        campaign_id=campaign.id,
        name="Lochagos",
        faction_id=faction.id,
        age=31,
    )
    campaign.commanders[commander.id] = commander
    campaign.commanders[subordinate.id] = subordinate

    stronghold = dm.Stronghold(
        id=dm.StrongholdID(1),
        campaign_id=campaign.id,
        hex_id=home_hex.id,
        type=StrongholdType.CITY,
        controlling_faction_id=faction.id,
        defensive_bonus=4,
        threshold=15,
        current_threshold=15,
        garrison_army_id=None,
    )
    campaign.strongholds[stronghold.id] = stronghold

    return campaign, stronghold, commander, subordinate


def test_start_and_complete_recruitment_creates_army():
    campaign, stronghold, commander, subordinate = _campaign_with_stronghold()

    order = dm.Order(
        id=dm.OrderID(1),
        campaign_id=campaign.id,
        army_id=None,
        commander_id=commander.id,
        order_type="raise_army",
        parameters={
            "stronghold_id": int(stronghold.id),
            "new_commander_id": int(subordinate.id),
            "infantry_unit_type_id": 1,
            "cavalry_unit_type_id": 2,
            "army_name": "1st Theme",
        },
        issued_at=_timestamp(1),
        execute_at=_timestamp(1),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    context = orders.OrderContext(campaign=campaign, day_part=DayPart.MORNING)
    pre_count = len(campaign.armies)
    result = orders.execute_order(context, order)

    assert result.status == OrderStatus.EXECUTING
    expected_complete_day = campaign.current_day + DEFAULT_RULES.recruitment.muster_duration_days
    assert order.execute_day == expected_complete_day
    project_id = int(order.parameters["_project_id"])
    assert project_id in campaign.recruitments

    project = campaign.recruitments[project_id]
    campaign.current_day = project.completes_on_day
    order.execute_day = campaign.current_day

    completion = orders.execute_order(context, order)
    assert completion.status == OrderStatus.COMPLETED
    assert project_id not in campaign.recruitments

    assert len(campaign.armies) == pre_count + 1
    raised = max(campaign.armies.values(), key=lambda army: int(army.id))
    assert raised.commander_id == subordinate.id
    assert sum(det.soldiers for det in raised.detachments) > 0
    assert raised.supplies_current == raised.daily_supply_consumption * 14


def test_recruitment_revolt_spawns_rebel_army():
    campaign, stronghold, commander, subordinate = _campaign_with_stronghold()
    home_hex = campaign.map.hexes[dm.HexID(1)]
    home_hex.last_recruited_day = campaign.current_day

    forced_rules = replace(
        DEFAULT_RULES,
        recruitment=RecruitmentRules(
            muster_duration_days=5,
            recruitment_cooldown_days=365,
            revolt_chance=6,
            recently_conquered_days=90,
        ),
    )

    order = dm.Order(
        id=dm.OrderID(2),
        campaign_id=campaign.id,
        army_id=None,
        commander_id=commander.id,
        order_type="raise_army",
        parameters={
            "stronghold_id": int(stronghold.id),
            "new_commander_id": int(subordinate.id),
            "infantry_unit_type_id": 1,
            "army_name": "2nd Theme",
        },
        issued_at=_timestamp(2),
        execute_at=_timestamp(2),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    context = orders.OrderContext(campaign=campaign, day_part=DayPart.MORNING, rules=forced_rules)
    result = orders.execute_order(context, order)
    assert result.status == OrderStatus.EXECUTING
    revolt_events = [
        evt for evt in (result.events or []) if evt.get("type") == "recruitment_revolt"
    ]
    assert revolt_events, "expected revolt event when chance forced to trigger"
    assert any(
        army.status_effects and army.status_effects.get("revolt")
        for army in campaign.armies.values()
    )
