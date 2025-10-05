"""Integration-style tests for the domain order execution layer."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest import mock

from cataphract.domain import models as dm
from cataphract.domain import orders, tick
from cataphract.domain.enums import (
    ArmyStatus,
    DayPart,
    OrderStatus,
    Season,
    SiegeStatus,
    StrongholdType,
)


def _base_campaign() -> tuple[dm.Campaign, dm.Army, dm.Commander, dm.Hex, dm.Hex]:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Test",
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
        terrain="flatland",
        settlement=60,
        controlling_faction_id=dm.FactionID(1),
    )
    target = dm.Hex(
        id=dm.HexID(2),
        campaign_id=campaign.id,
        q=1,
        r=0,
        terrain="flatland",
        settlement=80,
        controlling_faction_id=dm.FactionID(2),
    )
    campaign.map.hexes[origin.id] = origin
    campaign.map.hexes[target.id] = target

    unit_type = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="infantry",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
    )
    campaign.unit_types[unit_type.id] = unit_type

    commander = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="General",
        faction_id=dm.FactionID(1),
        age=40,
    )
    campaign.commanders[commander.id] = commander

    detachment = dm.Detachment(
        id=dm.DetachmentID(1),
        unit_type_id=unit_type.id,
        soldiers=600,
        wagons=0,
    )
    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=commander.id,
        current_hex_id=origin.id,
        detachments=[detachment],
        status=ArmyStatus.IDLE,
        supplies_current=8_000,
        status_effects={},
        noncombatant_count=150,
    )
    campaign.armies[army.id] = army

    return campaign, army, commander, origin, target


def _ts(day: int) -> datetime:
    return datetime(2025, 1, day, tzinfo=UTC)


def test_move_order_advances_army_hex():
    campaign, army, commander, _origin, target = _base_campaign()

    order = dm.Order(
        id=dm.OrderID(1),
        campaign_id=campaign.id,
        army_id=army.id,
        commander_id=commander.id,
        order_type="move",
        parameters={
            "movement_type": "standard",
            "legs": [
                {
                    "to_hex_id": int(target.id),
                    "distance_miles": 12,
                    "on_road": True,
                }
            ],
        },
        issued_at=_ts(1),
        execute_at=_ts(1),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    tick.run_daily_tick(campaign)

    assert army.current_hex_id == target.id
    assert order.status == OrderStatus.COMPLETED
    assert army.status == ArmyStatus.MARCHING
    assert campaign.current_day == 1


def test_forage_order_gains_supplies():
    campaign, army, commander, origin, target = _base_campaign()
    army.current_hex_id = origin.id
    starting_supplies = army.supplies_current

    order = dm.Order(
        id=dm.OrderID(2),
        campaign_id=campaign.id,
        army_id=army.id,
        commander_id=commander.id,
        order_type="forage",
        parameters={"hex_ids": [int(target.id)]},
        issued_at=_ts(2),
        execute_at=_ts(2),
        execute_day=campaign.current_day,
        execute_part=DayPart.MIDDAY,
    )
    campaign.orders[order.id] = order

    with mock.patch("cataphract.domain.orders.roll_dice") as mock_roll:
        mock_roll.side_effect = [
            {"total": 6},  # supply windfall
            {"total": 6},  # escape check (fail -> captured)
        ]
        tick.run_daily_tick(campaign)

    assert order.status == OrderStatus.COMPLETED
    assert army.status == ArmyStatus.FORAGING
    assert campaign.map.hexes[target.id].foraging_times_remaining == 4
    assert army.supplies_current > starting_supplies


def test_besiege_order_creates_siege():
    campaign, army, commander, _origin, target = _base_campaign()
    army.current_hex_id = target.id

    garrison = dm.Army(
        id=dm.ArmyID(2),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(2),
        current_hex_id=target.id,
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(2),
                unit_type_id=dm.UnitTypeID(1),
                soldiers=300,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=4_000,
        status_effects={},
        noncombatant_count=80,
    )
    campaign.armies[garrison.id] = garrison

    stronghold = dm.Stronghold(
        id=dm.StrongholdID(1),
        campaign_id=campaign.id,
        hex_id=target.id,
        type=StrongholdType.CITY,
        controlling_faction_id=dm.FactionID(2),
        defensive_bonus=4,
        threshold=15,
        current_threshold=15,
        gates_open=False,
        garrison_army_id=garrison.id,
    )
    campaign.strongholds[stronghold.id] = stronghold

    order = dm.Order(
        id=dm.OrderID(3),
        campaign_id=campaign.id,
        army_id=army.id,
        commander_id=commander.id,
        order_type="besiege",
        parameters={"stronghold_id": int(stronghold.id), "siege_engines": 2},
        issued_at=_ts(3),
        execute_at=_ts(3),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    with mock.patch("cataphract.domain.orders.roll_dice") as mock_roll:
        mock_roll.side_effect = [
            {"total": 6},  # supply windfall
            {"total": 6},  # escape check (fail -> captured)
        ]
        tick.run_daily_tick(campaign)

    assert order.status == OrderStatus.COMPLETED
    assert army.status == ArmyStatus.BESIEGING
    assert len(campaign.sieges) == 1
    siege = next(iter(campaign.sieges.values()))
    assert siege.stronghold_id == stronghold.id
    assert army.id in siege.attacker_army_ids


def test_assault_order_resolves_successful_battle():
    campaign, army, commander, _origin, target = _base_campaign()
    army.current_hex_id = target.id

    defender_commander = dm.Commander(
        id=dm.CommanderID(3),
        campaign_id=campaign.id,
        name="Captain",
        faction_id=dm.FactionID(2),
        age=35,
    )
    campaign.commanders[defender_commander.id] = defender_commander

    garrison = dm.Army(
        id=dm.ArmyID(4),
        campaign_id=campaign.id,
        commander_id=defender_commander.id,
        current_hex_id=target.id,
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(3),
                unit_type_id=dm.UnitTypeID(1),
                soldiers=300,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=2_000,
        status_effects={},
        noncombatant_count=60,
    )
    campaign.armies[garrison.id] = garrison

    stronghold = dm.Stronghold(
        id=dm.StrongholdID(2),
        campaign_id=campaign.id,
        hex_id=target.id,
        type=StrongholdType.CITY,
        controlling_faction_id=dm.FactionID(2),
        defensive_bonus=4,
        threshold=15,
        current_threshold=15,
        gates_open=False,
        garrison_army_id=garrison.id,
        loot_held=20_000,
        supplies_held=12_000,
    )
    campaign.strongholds[stronghold.id] = stronghold

    siege = dm.Siege(
        id=dm.SiegeID(1),
        stronghold_id=stronghold.id,
        attacker_army_ids=[army.id],
        defender_army_id=garrison.id,
        started_on_day=campaign.current_day,
        weeks_elapsed=0,
        current_threshold=stronghold.current_threshold,
        threshold_modifiers=[],
        siege_engines_count=2,
        attempts=[],
    )
    campaign.sieges[siege.id] = siege

    order = dm.Order(
        id=dm.OrderID(4),
        campaign_id=campaign.id,
        army_id=army.id,
        commander_id=commander.id,
        order_type="assault",
        parameters={
            "stronghold_id": int(stronghold.id),
            "attacker_fixed_roll": 12,
            "defender_fixed_roll": 2,
            "pillage": True,
        },
        issued_at=_ts(4),
        execute_at=_ts(4),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    campaign.orders[order.id] = order

    with mock.patch("cataphract.domain.orders.roll_dice") as mock_roll:
        mock_roll.side_effect = [
            {"total": 6},  # supply windfall
            {"total": 6},  # escape check (fail -> captured)
        ]
        tick.run_daily_tick(campaign)

    assert order.status == OrderStatus.COMPLETED
    assert stronghold.controlling_faction_id == commander.faction_id
    assert stronghold.gates_open is True
    assert campaign.sieges[siege.id].status == SiegeStatus.SUCCESSFUL_ASSAULT

    assert army.loot_carried > 0
    assert stronghold.garrison_army_id == army.id
    defender_commander = campaign.commanders[garrison.commander_id]
    assert defender_commander.status == "captured"


def test_supply_transfer_order_moves_supplies():
    campaign, army, commander, origin, _target = _base_campaign()
    army.supplies_current = 1_000
    target_army = dm.Army(
        id=dm.ArmyID(5),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(4),
        current_hex_id=origin.id,
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(4),
                unit_type_id=dm.UnitTypeID(1),
                soldiers=400,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=100,
        supplies_capacity=2_000,
        status_effects={},
    )
    campaign.armies[target_army.id] = target_army

    order = dm.Order(
        id=dm.OrderID(6),
        campaign_id=campaign.id,
        army_id=army.id,
        commander_id=commander.id,
        order_type="supply_transfer",
        parameters={"target_army_id": int(target_army.id), "amount": 300},
        issued_at=_ts(5),
        execute_at=_ts(5),
        execute_day=campaign.current_day,
        execute_part=DayPart.MORNING,
    )
    context = orders.OrderContext(campaign=campaign, day_part=DayPart.MORNING)
    result = orders.execute_order(context, order)

    assert result.status == OrderStatus.COMPLETED
    assert target_army.supplies_current == 400
    assert army.supplies_current == 700


def test_night_march_wrong_fork_diverts():
    campaign, army, commander, _origin, target = _base_campaign()
    with mock.patch("cataphract.domain.movement.should_take_wrong_fork", return_value=True):
        alt_hex = dm.Hex(
            id=dm.HexID(3),
            campaign_id=campaign.id,
            q=0,
            r=1,
            terrain="flatland",
            settlement=40,
            controlling_faction_id=dm.FactionID(1),
        )
        campaign.map.hexes[alt_hex.id] = alt_hex

        order = dm.Order(
            id=dm.OrderID(99),
            campaign_id=campaign.id,
            army_id=army.id,
            commander_id=commander.id,
            order_type="move",
            parameters={
                "movement_type": "night",
                "legs": [
                    {
                        "to_hex_id": int(target.id),
                        "distance_miles": 6,
                        "on_road": True,
                        "has_fork": True,
                        "alternate_hex_id": int(alt_hex.id),
                    }
                ],
            },
            issued_at=_ts(6),
            execute_at=_ts(6),
            execute_day=campaign.current_day,
            execute_part=DayPart.MORNING,
        )
        campaign.orders[order.id] = order

        tick.run_daily_tick(campaign)

    assert army.current_hex_id == alt_hex.id
    assert order.status == OrderStatus.COMPLETED
