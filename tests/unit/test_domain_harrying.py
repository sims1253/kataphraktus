"""Tests for the harrying subsystem."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest import mock

from cataphract.domain import harrying, orders
from cataphract.domain import models as dm
from cataphract.domain.enums import ArmyStatus, DayPart, OrderStatus, Season


def _timestamp(day: int) -> datetime:
    return datetime(2025, 1, day, tzinfo=UTC)


def _armies_for_harrying() -> tuple[dm.Campaign, dm.Army, dm.Army]:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Harry Test",
        start_date=date(1325, 5, 12),
        current_day=0,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )

    unit_cav = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="cavalry",
        category="cavalry",
        battle_multiplier=2.0,
        supply_cost_per_day=10,
        can_travel_offroad=True,
        special_abilities={"skirmisher": True},
    )
    campaign.unit_types[unit_cav.id] = unit_cav

    commander_att = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="Attacker",
        faction_id=dm.FactionID(1),
        age=30,
    )
    commander_def = dm.Commander(
        id=dm.CommanderID(2),
        campaign_id=campaign.id,
        name="Defender",
        faction_id=dm.FactionID(2),
        age=31,
    )
    campaign.commanders[commander_att.id] = commander_att
    campaign.commanders[commander_def.id] = commander_def

    attacker = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=commander_att.id,
        current_hex_id=dm.HexID(1),
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(1),
                unit_type_id=unit_cav.id,
                soldiers=200,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=2_000,
        supplies_capacity=10_000,
        daily_supply_consumption=500,
        noncombatant_count=40,
    )
    defender = dm.Army(
        id=dm.ArmyID(2),
        campaign_id=campaign.id,
        commander_id=commander_def.id,
        current_hex_id=dm.HexID(2),
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(2),
                unit_type_id=unit_cav.id,
                soldiers=300,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=5_000,
        supplies_capacity=12_000,
        daily_supply_consumption=600,
        noncombatant_count=60,
        loot_carried=1_000,
    )
    campaign.armies[attacker.id] = attacker
    campaign.armies[defender.id] = defender

    return campaign, attacker, defender


def test_harrying_success_torches_supplies():
    campaign, attacker, defender = _armies_for_harrying()

    with mock.patch("cataphract.domain.harrying.roll_dice") as mock_roll:
        mock_roll.side_effect = [
            {"total": 1},  # success check
            {"total": 5},  # torch roll
        ]
        result = harrying.resolve_harrying(
            campaign,
            attacker,
            defender,
            attacker.detachments,
            options=harrying.HarryingOptions(objective="torch"),
        )

    assert result.success is True
    expected_burn = 200 * (5 + 3)  # base roll + skirmisher/cavalry modifiers
    assert result.supplies_burned == expected_burn
    assert defender.supplies_current == 5_000 - expected_burn
    assert attacker.status == ArmyStatus.HARRYING


def test_harried_army_cannot_rest():
    campaign, attacker, _defender = _armies_for_harrying()

    attacker.status_effects = {"harried": {"day": campaign.current_day}}
    order = dm.Order(
        id=dm.OrderID(10),
        campaign_id=campaign.id,
        army_id=attacker.id,
        commander_id=attacker.commander_id,
        order_type="rest",
        parameters={},
        issued_at=_timestamp(1),
        execute_at=_timestamp(1),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    context = orders.OrderContext(campaign=campaign, day_part=DayPart.MORNING)
    outcome = orders.execute_order(context, order)
    assert outcome.status == OrderStatus.FAILED
    assert "harried" in (outcome.detail or "")


def test_harrying_failure_costs_detachment():
    campaign, attacker, defender = _armies_for_harrying()

    with mock.patch("cataphract.domain.harrying.roll_dice") as mock_roll:
        mock_roll.side_effect = [
            {"total": 6},  # failure roll
        ]
        result = harrying.resolve_harrying(
            campaign,
            attacker,
            defender,
            attacker.detachments,
            options=harrying.HarryingOptions(objective="kill"),
        )

    assert result.success is False
    assert attacker.detachments[0].soldiers < 200
    assert result.attacker_losses > 0
