"""Daily tick orchestration for Cataphract campaigns."""

from __future__ import annotations

from collections.abc import Iterable

from cataphract.domain import mercenaries as mercenary_rules
from cataphract.domain import messaging, morale, naval, supply
from cataphract.domain import orders as order_rules
from cataphract.domain import siege as siege_rules
from cataphract.domain.enums import ArmyStatus, DayPart, OrderStatus
from cataphract.domain.models import Campaign, Order
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig

DAY_PART_SEQUENCE: tuple[DayPart, ...] = (
    DayPart.MORNING,
    DayPart.MIDDAY,
    DayPart.EVENING,
    DayPart.NIGHT,
)

DAY_PART_FRACTION = 1 / len(DAY_PART_SEQUENCE)

FORCED_MARCH_MORALE_INTERVAL = 7


def run_daily_tick(
    campaign: Campaign,
    *,
    rules: RulesConfig = DEFAULT_RULES,
) -> None:
    """Advance the campaign by one in-game day."""

    _start_of_day(campaign, rules)

    for part in DAY_PART_SEQUENCE:
        campaign.current_part = part
        _advance_messages(campaign, rules)
        _advance_naval_movements(campaign, rules)
        _execute_orders_for_part(campaign, part, rules)

    _consume_supplies(campaign, rules)
    mercenary_rules.process_daily_upkeep(campaign, rules=rules)

    if (campaign.current_day + 1) % FORCED_MARCH_MORALE_INTERVAL == 0:
        _advance_sieges(campaign, rules)

    campaign.current_day += 1
    campaign.current_part = DayPart.MORNING


def _start_of_day(campaign: Campaign, rules: RulesConfig) -> None:
    """Reset transient state at the beginning of the day."""

    for army in campaign.armies.values():
        snapshot = supply.build_supply_snapshot(campaign, army, rules)
        army.supplies_capacity = snapshot.capacity
        army.daily_supply_consumption = snapshot.consumption
        army.noncombatant_count = snapshot.noncombatants
        army.column_length_miles = snapshot.column_length_miles
        army.movement_points_remaining = 1.0

        if campaign.current_day % FORCED_MARCH_MORALE_INTERVAL == 0:
            army.days_marched_this_week = 0

        if army.status in (
            ArmyStatus.MARCHING,
            ArmyStatus.FORCED_MARCH,
            ArmyStatus.NIGHT_MARCH,
            ArmyStatus.HARRYING,
        ):
            army.status = ArmyStatus.IDLE

        if army.status == ArmyStatus.RESTING and army.rest_duration_days is not None:
            days_elapsed = campaign.current_day - (army.rest_started_day or campaign.current_day)
            if days_elapsed >= army.rest_duration_days:
                army.rest_duration_days = None
                army.rest_started_day = None
                army.status = ArmyStatus.IDLE

        if army.forced_march_days >= FORCED_MARCH_MORALE_INTERVAL:
            penalties = int(army.forced_march_days // FORCED_MARCH_MORALE_INTERVAL)
            morale.adjust_morale(
                army,
                -penalties * rules.morale.forced_march_morale_loss_per_week,
            )
            army.forced_march_days = army.forced_march_days % FORCED_MARCH_MORALE_INTERVAL


def _execute_orders_for_part(
    campaign: Campaign,
    part: DayPart,
    rules: RulesConfig,
) -> None:
    """Execute all orders scheduled for the supplied day part."""

    context = order_rules.OrderContext(campaign=campaign, day_part=part, rules=rules)
    for order in _orders_due(campaign.orders.values(), campaign.current_day, part):
        result = order_rules.execute_order(context, order)
        if result.status in {OrderStatus.COMPLETED, OrderStatus.FAILED}:
            order.execute_day = campaign.current_day


def _orders_due(
    orders: Iterable[Order],
    current_day: int,
    part: DayPart,
) -> list[Order]:
    """Return orders scheduled for the current day and part, sorted by issue time."""

    due: list[Order] = []
    for order in orders:
        if order.status not in (OrderStatus.PENDING, OrderStatus.EXECUTING):
            continue
        execute_day = order.execute_day if order.execute_day is not None else current_day
        if execute_day != current_day:
            continue
        execute_part = order.execute_part or DayPart.MORNING
        if execute_part != part:
            continue
        due.append(order)

    return sorted(due, key=lambda order: order.issued_at)


def _consume_supplies(
    campaign: Campaign,
    rules: RulesConfig,
) -> None:
    for army in campaign.armies.values():
        consumption = army.daily_supply_consumption
        if army.supplies_current >= consumption:
            army.supplies_current -= consumption
            army.days_without_supplies = 0
        else:
            army.supplies_current = 0
            army.days_without_supplies += 1
            morale.adjust_morale(army, -rules.morale.starvation_morale_loss_per_day)
            seed = f"starvation:{int(army.id)}:{campaign.current_day}"
            success, roll = morale.roll_morale_check(army.morale_current, seed)
            if not success:
                commander = campaign.commanders.get(army.commander_id)
                traits = commander.traits if commander else []
                morale.apply_morale_consequence(
                    army,
                    roll,
                    traits,
                    seed=f"{seed}:consequence",
                    current_day=campaign.current_day,
                )
            if army.days_without_supplies >= rules.morale.starvation_dissolution_days:
                army.status = ArmyStatus.ROUTED


def _advance_sieges(campaign: Campaign, rules: RulesConfig) -> None:
    for siege in campaign.sieges.values():
        siege_rules.advance_siege(siege, rules=rules)


def _advance_messages(campaign: Campaign, rules: RulesConfig) -> None:
    messaging.advance_messages(campaign, rules=rules, day_fraction=DAY_PART_FRACTION)


def _advance_naval_movements(campaign: Campaign, rules: RulesConfig) -> None:
    naval.advance_ships(campaign, rules=rules, day_fraction=DAY_PART_FRACTION)
