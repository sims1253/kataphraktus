"""Order execution rules for Cataphract campaigns."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from cataphract.domain import (
    battle,
    harrying,
    messaging,
    morale,
    movement,
    naval,
    operations,
    recruitment,
    supply,
)
from cataphract.domain.enums import (
    ArmyStatus,
    DayPart,
    MovementType,
    OperationType,
    OrderStatus,
    SiegeStatus,
)
from cataphract.domain.models import (
    Army,
    Campaign,
    CommanderID,
    Detachment,
    HexID,
    Message,
    MessageID,
    MovementLeg,
    MovementLegID,
    Operation,
    OperationID,
    Order,
    Siege,
    SiegeID,
    Stronghold,
    StrongholdID,
    UnitType,
    UnitTypeID,
)
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice

COMMANDER_ESCAPE_THRESHOLD = 3


@dataclass(slots=True)
class OrderContext:
    """Shared context passed to every order handler."""

    campaign: Campaign
    day_part: DayPart
    rules: RulesConfig = DEFAULT_RULES


@dataclass(slots=True)
class OrderExecutionResult:
    """Outcome of an order execution."""

    status: OrderStatus
    detail: str | None = None
    events: list[dict[str, object]] = field(default_factory=list)


OrderHandler = Callable[[OrderContext, Order, Army | None], OrderExecutionResult]


class OrderExecutionError(RuntimeError):
    """Raised when an order cannot be executed."""


@dataclass(slots=True)
class MovementPlan:
    """Computed details for executing a movement order."""

    movement_type: MovementType
    legs: list[MovementLeg]
    total_fraction: float
    final_hex: HexID
    diverted: bool = False
    diversion_detail: str | None = None


def execute_order(context: OrderContext, order: Order) -> OrderExecutionResult:
    """Execute a pending order using the registered handler."""

    if order.status not in (OrderStatus.PENDING, OrderStatus.EXECUTING):
        return OrderExecutionResult(order.status, "order already resolved")

    handler = _ORDER_HANDLERS.get(order.order_type)
    if handler is None:
        detail = f"unsupported order type: {order.order_type}"
        order.status = OrderStatus.FAILED
        order.result = {"detail": detail}
        return OrderExecutionResult(OrderStatus.FAILED, detail)

    army: Army | None = None
    if order.army_id is not None:
        army = context.campaign.armies.get(order.army_id)
        if army is None:
            detail = f"army {int(order.army_id)} not found"
            order.status = OrderStatus.FAILED
            order.result = {"detail": detail}
            return OrderExecutionResult(OrderStatus.FAILED, detail)

    order.status = OrderStatus.EXECUTING
    result = handler(context, order, army)
    order.status = result.status
    if result.detail or result.events:
        order.result = {"detail": result.detail, "events": result.events}
    else:
        order.result = None
    return result


# ---------------------------------------------------------------------------
# Registered order handlers


def _handle_move(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("movement order requires an army")

    try:
        plan = _prepare_movement_plan(context, army, order)
    except OrderExecutionError as exc:
        return _failure(str(exc))

    army.current_hex_id = plan.final_hex
    army.destination_hex_id = None
    army.movement_points_remaining = max(0.0, 1.0 - plan.total_fraction)
    army.days_marched_this_week += 1
    army.status = (
        ArmyStatus.FORCED_MARCH
        if plan.movement_type == MovementType.FORCED
        else ArmyStatus.NIGHT_MARCH
        if plan.movement_type == MovementType.NIGHT or any(leg.is_night for leg in plan.legs)
        else ArmyStatus.MARCHING
    )
    if plan.movement_type == MovementType.FORCED:
        army.forced_march_days += plan.total_fraction

    detail = f"moved to hex {int(plan.final_hex)} via {len(plan.legs)} leg(s)"
    if plan.diverted and plan.diversion_detail:
        detail += f" ({plan.diversion_detail})"
    return OrderExecutionResult(OrderStatus.COMPLETED, detail)


def _handle_rest(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("rest order requires an army")

    status_effects = army.status_effects or {}
    harried = status_effects.get("harried")
    if isinstance(harried, dict):
        harried_map = cast(dict[str, object], harried)
        if harried_map.get("day") == context.campaign.current_day:
            return _failure("army is harried and cannot rest today")

    duration = int(order.parameters.get("duration_days", 1))
    if duration <= 0:
        return _failure("rest duration must be positive")

    army.status = ArmyStatus.RESTING
    army.rest_duration_days = duration
    army.rest_started_day = context.campaign.current_day
    army.days_marched_this_week = 0
    army.movement_points_remaining = 0.0
    army.destination_hex_id = None
    morale.adjust_morale(army, max(0, army.morale_resting - army.morale_current))

    detail = f"resting for {duration} day(s)"
    return OrderExecutionResult(OrderStatus.COMPLETED, detail)


def _handle_forage(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("forage order requires an army")

    hex_ids = _hex_id_list(order.parameters.get("hex_ids"))
    if not hex_ids:
        return _failure("forage order missing hex_ids")

    outcome = supply.forage(context.campaign, army, hex_ids)
    detail = f"foraged {len(outcome.foraged_hexes)} hex(es)"
    if outcome.supplies_gained:
        detail += f" gaining {outcome.supplies_gained} supplies"
    if outcome.revolt_triggered:
        detail += "; revolt triggered"
    status = OrderStatus.COMPLETED if outcome.success else OrderStatus.FAILED
    army.status = ArmyStatus.FORAGING if outcome.success else army.status
    return OrderExecutionResult(status, detail)


def _handle_torch(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("torch order requires an army")

    hex_ids = _hex_id_list(order.parameters.get("hex_ids"))
    if not hex_ids:
        return _failure("torch order missing hex_ids")

    outcome = supply.torch(context.campaign, army, hex_ids)
    detail = f"torched {len(outcome.torched_hexes)} hex(es)"
    if outcome.revolt_triggered:
        detail += "; revolt triggered"
    status = OrderStatus.COMPLETED if outcome.success else OrderStatus.FAILED
    army.status = ArmyStatus.TORCHING if outcome.success else army.status
    return OrderExecutionResult(status, detail)


def _handle_supply_transfer(
    context: OrderContext, order: Order, army: Army | None
) -> OrderExecutionResult:
    if army is None:
        return _failure("supply transfer requires an army")

    target_id_raw = order.parameters.get("target_army_id")
    amount_raw = order.parameters.get("amount")
    try:
        target_id = int(target_id_raw)
        amount = int(amount_raw)
    except (TypeError, ValueError):
        return _failure("supply transfer requires target_army_id and amount")

    if amount <= 0:
        return _failure("transfer amount must be positive")

    target = context.campaign.armies.get(target_id)
    if target is None:
        return _failure("target army not found")

    available = min(amount, army.supplies_current)
    capacity = max(0, target.supplies_capacity - target.supplies_current)
    transfer_amount = min(available, capacity)
    if transfer_amount <= 0:
        return _failure("no supplies transferable")

    army.supplies_current -= transfer_amount
    target.supplies_current += transfer_amount

    detail = f"transferred {transfer_amount} supplies to army {target_id}"
    return OrderExecutionResult(OrderStatus.COMPLETED, detail)


def _handle_besiege(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("besiege order requires an army")

    stronghold_id_raw = order.parameters.get("stronghold_id")
    try:
        stronghold_id = StrongholdID(int(stronghold_id_raw))
    except (TypeError, ValueError):
        return _failure("besiege order missing stronghold_id")

    stronghold = context.campaign.strongholds.get(stronghold_id)
    if stronghold is None:
        return _failure("stronghold not found")

    try:
        siege_engines_count = _maybe_int(
            order.parameters.get("siege_engines"), "siege_engines must be an int"
        )
    except OrderExecutionError as exc:
        return _failure(str(exc))
    siege_engines_value = siege_engines_count or 0

    existing = _find_siege_by_stronghold(context.campaign, stronghold_id)
    if existing is None:
        siege_id = _next_siege_id(context.campaign)
        existing = Siege(
            id=siege_id,
            stronghold_id=stronghold_id,
            attacker_army_ids=[army.id],
            defender_army_id=stronghold.garrison_army_id,
            started_on_day=context.campaign.current_day,
            weeks_elapsed=0,
            current_threshold=stronghold.current_threshold,
            threshold_modifiers=[],
            siege_engines_count=siege_engines_value,
            attempts=[],
        )
        context.campaign.sieges[existing.id] = existing
    elif army.id not in existing.attacker_army_ids:
        existing.attacker_army_ids.append(army.id)

    army.status = ArmyStatus.BESIEGING
    detail = f"besieging stronghold {int(stronghold_id)}"
    return OrderExecutionResult(OrderStatus.COMPLETED, detail)


def _handle_assault(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("assault order requires an army")

    try:
        stronghold, defender_army, siege, options = _prepare_assault_context(context, order)
    except OrderExecutionError as exc:
        return _failure(str(exc))

    army.status = ArmyStatus.IN_BATTLE
    defender_army.status = ArmyStatus.IN_BATTLE

    result = battle.resolve_battle(
        army,
        defender_army,
        unit_types=context.campaign.unit_types,
        options=options,
        rules=context.rules,
    )
    _apply_additional_losses(defender_army if result.winner == "attacker" else army, 0.10)

    events: list[dict[str, object]] = []
    detail_parts = [f"assault result: {result.winner}"]

    if result.winner == "attacker":
        pillage_flag = _is_truthy(order.parameters.get("pillage"))
        capture_detail, capture_events = _resolve_stronghold_capture(
            CaptureContext(
                campaign=context.campaign,
                attacker=army,
                defender=defender_army,
                stronghold=stronghold,
                siege=siege,
            ),
            pillage_flag,
        )
        if capture_detail:
            detail_parts.append(capture_detail)
        if capture_events:
            events.extend(capture_events)
    if army.status != ArmyStatus.ROUTED:
        army.status = ArmyStatus.IDLE
    if result.winner == "attacker":
        defender_army.status = ArmyStatus.ROUTED
    elif defender_army.status != ArmyStatus.ROUTED:
        defender_army.status = ArmyStatus.IDLE
    return OrderExecutionResult(OrderStatus.COMPLETED, "; ".join(detail_parts), events)


def _resolve_stronghold_capture(
    capture: CaptureContext,
    pillage_flag: bool,
) -> tuple[str | None, list[dict[str, object]]]:
    commander = capture.campaign.commanders.get(capture.attacker.commander_id)
    _transfer_control(capture.stronghold, capture.siege, commander, capture.attacker)

    events: list[dict[str, object]] = []
    detail_parts: list[str] = []

    detail = _apply_capture_supplies(capture.stronghold, capture.attacker, capture.siege)
    if detail is not None:
        detail_parts.append(detail.detail)
        if detail.event is not None:
            events.append(detail.event)

    detail = _apply_noncombatant_gain(capture.stronghold, capture.attacker)
    if detail is not None:
        detail_parts.append(detail.detail)
        if detail.event is not None:
            events.append(detail.event)

    pillage_detail = _handle_post_capture_behavior(
        pillage_flag,
        capture.campaign,
        commander,
        capture.attacker,
        capture.stronghold,
    )
    if pillage_detail is not None:
        detail_parts.append(pillage_detail.detail)
        if pillage_detail.event is not None:
            events.append(pillage_detail.event)

    fate_detail = _resolve_defender_commander(capture.campaign, capture.defender, commander)
    if fate_detail is not None:
        detail_parts.append(fate_detail.detail)
        if fate_detail.event is not None:
            events.append(fate_detail.event)

    return ("; ".join(detail_parts) if detail_parts else None, events)


def _transfer_control(
    stronghold: Stronghold,
    siege: Siege | None,
    commander,
    army: Army,
) -> None:
    if commander is not None:
        stronghold.controlling_faction_id = commander.faction_id
    stronghold.gates_open = True
    stronghold.garrison_army_id = army.id
    if siege is not None:
        siege.status = SiegeStatus.SUCCESSFUL_ASSAULT


def _apply_capture_supplies(
    stronghold: Stronghold,
    army: Army,
    siege: Siege | None,
) -> CaptureOutcome | None:
    supply_gain = _calculate_capture_supply(stronghold, siege)
    if supply_gain <= 0:
        return None

    capacity_remaining = max(0, army.supplies_capacity - army.supplies_current)
    loaded = min(supply_gain, capacity_remaining)
    if loaded:
        army.supplies_current += loaded
    stored = supply_gain - loaded
    if stored:
        stronghold.supplies_held += stored
    detail = f"captured {supply_gain} supplies"
    if loaded:
        detail += f" ({loaded} loaded)"
    event = {
        "type": "capture_supplies",
        "amount": supply_gain,
        "loaded": loaded,
        "stored": stored,
    }
    return CaptureOutcome(detail=detail, event=event)


def _apply_noncombatant_gain(stronghold: Stronghold, army: Army) -> CaptureOutcome | None:
    ratio = _capture_noncombatant_ratio(stronghold.type)
    if ratio <= 0:
        return None

    base_pool = army.noncombatant_count or sum(det.soldiers for det in army.detachments)
    gain = max(1, round(base_pool * ratio))
    army.noncombatant_count += gain
    return CaptureOutcome(
        detail=f"gained {gain} camp followers",
        event={"type": "noncombatant_gain", "amount": gain},
    )


def _handle_post_capture_behavior(
    pillage_flag: bool,
    campaign: Campaign,
    commander,
    army: Army,
    stronghold: Stronghold,
) -> CaptureOutcome | None:
    if pillage_flag:
        loot_taken = stronghold.loot_held // 2
        stronghold.loot_held -= loot_taken
        army.loot_carried += loot_taken

        supplies_taken = stronghold.supplies_held // 2
        stronghold.supplies_held -= supplies_taken
        capacity = max(0, army.supplies_capacity - army.supplies_current)
        loaded = min(supplies_taken, capacity)
        if loaded:
            army.supplies_current += loaded

        morale.adjust_morale(army, 2, max_morale=army.morale_max)
        event = {"type": "pillage", "loot": loot_taken, "supplies": loaded}
        return CaptureOutcome(
            detail=f"pillage authorised ({loot_taken} loot, {loaded} supplies)",
            event=event,
        )

    seed = f"discipline:{int(army.id)}:{campaign.current_day}"
    success, morale_roll = morale.roll_morale_check(army.morale_current, seed)
    if success:
        return None

    traits = commander.traits if commander else []
    morale.apply_morale_consequence(
        army,
        morale_roll,
        traits,
        seed=f"{seed}:consequence",
        current_day=campaign.current_day,
    )
    return CaptureOutcome(
        detail="discipline check failed",
        event={"type": "discipline_failed", "roll": morale_roll},
    )


def _resolve_defender_commander(
    campaign: Campaign,
    defender_army: Army,
    attacker_commander,
) -> CaptureOutcome | None:
    defender_commander = campaign.commanders.get(defender_army.commander_id)
    if defender_commander is None:
        return None

    escape_roll = roll_dice(
        f"assault-escape:{int(defender_commander.id)}:{campaign.current_day}",
        "1d6",
    )["total"]
    if escape_roll <= COMMANDER_ESCAPE_THRESHOLD:
        defender_commander.status = "escaped"
        defender_commander.current_hex_id = None
        return CaptureOutcome(
            detail="defender commander escaped",
            event={
                "type": "commander_escaped",
                "commander_id": int(defender_commander.id),
            },
        )

    defender_commander.status = "captured"
    if attacker_commander is not None:
        defender_commander.captured_by_faction_id = attacker_commander.faction_id
    return CaptureOutcome(
        detail="defender commander captured",
        event={
            "type": "commander_captured",
            "commander_id": int(defender_commander.id),
        },
    )


def _calculate_capture_supply(stronghold: Stronghold, siege: Siege | None) -> int:
    weeks = siege.weeks_elapsed if siege is not None else 0
    multiplier_map = {
        "town": 10_000,
        "city": 100_000,
        "fortress": 1_000,
    }
    multiplier = multiplier_map.get(stronghold.type.value, 0)
    if multiplier <= 0:
        return 0
    roll = roll_dice(f"capture-supply:{int(stronghold.id)}:{weeks}", "1d6")["total"]
    return max(0, roll - weeks) * multiplier


def _capture_noncombatant_ratio(stronghold_type) -> float:
    mapping = {
        "fortress": 0.05,
        "town": 0.10,
        "city": 0.15,
    }
    return mapping.get(
        stronghold_type.value if hasattr(stronghold_type, "value") else str(stronghold_type), 0.0
    )


def _is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _handle_embark(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    if army is None:
        return _failure("embark order requires an army")

    ship_id_raw = order.parameters.get("ship_id")
    try:
        ship_id = int(ship_id_raw)
    except (TypeError, ValueError):
        return _failure("embark order missing ship_id")

    ship = context.campaign.ships.get(ship_id)
    if ship is None:
        return _failure("ship not found")

    result = naval.embark_army(context.campaign, army, ship, rules=context.rules)
    status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
    return OrderExecutionResult(status, result.detail)


def _handle_disembark(
    context: OrderContext, order: Order, army: Army | None
) -> OrderExecutionResult:
    if army is None:
        return _failure("disembark order requires an army")

    ship_id_raw = order.parameters.get("ship_id")
    try:
        ship_id = int(ship_id_raw)
    except (TypeError, ValueError):
        return _failure("disembark order missing ship_id")

    ship = context.campaign.ships.get(ship_id)
    if ship is None:
        return _failure("ship not found")

    result = naval.disembark_army(context.campaign, army, ship, rules=context.rules)
    status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
    return OrderExecutionResult(status, result.detail)


def _handle_naval_move(
    context: OrderContext, order: Order, _army: Army | None
) -> OrderExecutionResult:
    ship_id_raw = order.parameters.get("ship_id")
    try:
        ship_id = int(ship_id_raw)
    except (TypeError, ValueError):
        return _failure("naval move requires ship_id")

    ship = context.campaign.ships.get(ship_id)
    if ship is None:
        return _failure("ship not found")

    route_values = order.parameters.get("route")
    if not isinstance(route_values, list) or not route_values:
        return _failure("naval move requires route")

    route: list[HexID] = []
    for value in route_values:
        try:
            route.append(HexID(int(value)))
        except (TypeError, ValueError):
            return _failure("invalid hex id in route")

    result = naval.set_course(context.campaign, ship, route, rules=context.rules)
    status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
    return OrderExecutionResult(status, result.detail)


def _handle_send_message(
    context: OrderContext,
    order: Order,
    army: Army | None,
) -> OrderExecutionResult:
    recipient_raw = order.parameters.get("recipient_id")
    content = order.parameters.get("content", "")
    territory = order.parameters.get("territory_type", "friendly")

    try:
        recipient_id = CommanderID(int(recipient_raw))
    except (TypeError, ValueError):
        return _failure("send_message requires recipient_id")

    message_id = _next_message_id(context.campaign)
    sender_commander = order.commander_id if army is None else army.commander_id
    message = Message(
        id=message_id,
        campaign_id=context.campaign.id,
        sender_id=sender_commander,
        recipient_id=recipient_id,
        content=str(content),
        sent_at=order.issued_at,
        delivered_at=None,
        travel_time_days=0.0,
        territory_type=str(territory).lower(),
        status="pending",
        legs=[],
        days_remaining=0.0,
        failure_reason=None,
    )

    from_hex = army.current_hex_id if army else None
    recipient_commander = context.campaign.commanders.get(recipient_id)
    to_hex = recipient_commander.current_hex_id if recipient_commander else None

    result = messaging.dispatch_message(
        context.campaign,
        message,
        rules=context.rules,
        from_hex=int(from_hex) if from_hex is not None else None,
        to_hex=int(to_hex) if to_hex is not None else None,
    )
    status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
    return OrderExecutionResult(status, result.detail)


def _handle_raise_army(
    context: OrderContext, order: Order, _army: Army | None
) -> OrderExecutionResult:
    project_id = order.parameters.get("_project_id")
    if project_id is None:
        return _start_raise_army(context, order)
    return _complete_raise_army(context, order, project_id)


@dataclass(slots=True)
class RaiseArmySetup:
    """Validated data needed to begin a recruitment project."""

    recruitment_input: recruitment.RecruitmentInput
    infantry_type_id: UnitTypeID
    cavalry_type_id: UnitTypeID | None
    army_name: str


@dataclass(slots=True)
class CaptureContext:
    """Inputs required to resolve a successful assault."""

    campaign: Campaign
    attacker: Army
    defender: Army
    stronghold: Stronghold
    siege: Siege | None


@dataclass(slots=True)
class CaptureOutcome:
    """Result of a capture-related helper."""

    detail: str
    event: dict[str, object] | None = None


def _start_raise_army(context: OrderContext, order: Order) -> OrderExecutionResult:
    try:
        setup = _prepare_raise_army_setup(context, order)
    except ValueError as exc:
        return _failure(str(exc))

    try:
        result = recruitment.start_recruitment(
            context.campaign,
            setup.recruitment_input,
            rules=context.rules,
        )
    except ValueError as exc:
        return _failure(str(exc))

    order.parameters["_project_id"] = result.project.id
    order.parameters["infantry_unit_type_id"] = int(setup.infantry_type_id)
    if setup.cavalry_type_id is not None:
        order.parameters["_cavalry_type_id"] = int(setup.cavalry_type_id)
    order.parameters.setdefault("army_name", setup.army_name)
    order.execute_day = result.project.completes_on_day

    events: list[dict[str, object]] = []
    if result.revolts:
        events.append(
            {
                "type": "recruitment_revolt",
                "army_ids": [int(army.id) for army in result.revolts],
            }
        )
    return OrderExecutionResult(OrderStatus.EXECUTING, result.detail, events)


def _complete_raise_army(
    context: OrderContext, order: Order, project_id_value
) -> OrderExecutionResult:
    campaign = context.campaign
    try:
        project = campaign.recruitments[int(project_id_value)]
    except (KeyError, ValueError):
        return _failure("recruitment project missing")

    if campaign.current_day < project.completes_on_day:
        remaining = project.completes_on_day - campaign.current_day
        order.execute_day = project.completes_on_day
        detail = f"recruitment in progress; {remaining} day(s) remaining"
        return OrderExecutionResult(OrderStatus.EXECUTING, detail)

    try:
        infantry_type = _lookup_unit_type(context, order.parameters.get("infantry_unit_type_id"))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    cavalry_type_value = order.parameters.get("_cavalry_type_id")
    cavalry_type = None
    if cavalry_type_value is not None:
        cavalry_type = _lookup_unit_type(context, cavalry_type_value)
        if isinstance(cavalry_type, OrderExecutionResult):
            raise ValueError(cavalry_type.detail or "unit type not found")

    options = recruitment.RecruitmentCompletionOptions(
        army_name=str(order.parameters.get("army_name", "Raised Army")),
        infantry_type=infantry_type,
        cavalry_type=cavalry_type,
        rules=context.rules,
    )

    try:
        completion = recruitment.complete_recruitment(campaign, project, options)
    except ValueError as exc:
        return _failure(str(exc))

    return OrderExecutionResult(OrderStatus.COMPLETED, completion.detail)


def _prepare_raise_army_setup(
    context: OrderContext,
    order: Order,
) -> RaiseArmySetup:
    campaign = context.campaign

    try:
        stronghold = _lookup_stronghold(context, order.parameters.get("stronghold_id"))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    commander_id_value = _safe_int(order.parameters.get("new_commander_id"))
    if commander_id_value is None:
        raise ValueError("commander not found")
    commander = campaign.commanders.get(CommanderID(commander_id_value))
    if commander is None:
        raise ValueError("commander not found")

    try:
        infantry_type = _lookup_unit_type(context, order.parameters.get("infantry_unit_type_id"))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    cavalry_type_id_value = order.parameters.get("cavalry_unit_type_id")
    cavalry_type_id = None
    if cavalry_type_id_value is not None:
        cavalry_type = _lookup_unit_type(context, cavalry_type_id_value)
        cavalry_type_id = cavalry_type.id

    rally_target = order.parameters.get("rally_hex_id") or order.parameters.get("stronghold_id")
    try:
        rally_hex_key = HexID(int(rally_target))
    except (TypeError, ValueError) as exc:
        raise ValueError("rally hex not found") from exc
    rally_hex = campaign.map.hexes.get(rally_hex_key)
    if rally_hex is None:
        raise ValueError("rally hex not found")

    army_name = str(order.parameters.get("army_name", commander.name))

    recruitment_input = recruitment.RecruitmentInput(
        stronghold=stronghold,
        commander=commander,
        rally_hex=rally_hex,
        pending_order_id=order.id,
    )

    return RaiseArmySetup(
        recruitment_input=recruitment_input,
        infantry_type_id=infantry_type.id,
        cavalry_type_id=cavalry_type_id,
        army_name=army_name,
    )


def _lookup_unit_type(context: OrderContext, raw_value) -> UnitType:
    try:
        type_id = UnitTypeID(int(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError("unit type id must be an int") from exc

    unit_type = context.campaign.unit_types.get(type_id)
    if unit_type is None:
        raise ValueError("unit type not found")
    return unit_type


def _lookup_stronghold(context: OrderContext, raw_value) -> Stronghold:
    try:
        stronghold_id = StrongholdID(int(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError("stronghold_id must be an int") from exc

    stronghold = context.campaign.strongholds.get(stronghold_id)
    if stronghold is None:
        raise ValueError("stronghold not found")
    return stronghold


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _handle_launch_operation(
    context: OrderContext,
    order: Order,
    _army: Army | None,
) -> OrderExecutionResult:
    operation = None
    operation_id_raw = order.parameters.get("operation_id")
    if operation_id_raw is not None:
        try:
            op_id = OperationID(int(operation_id_raw))
        except (TypeError, ValueError):
            return _failure("invalid operation_id")
        operation = context.campaign.operations.get(op_id)

    if operation is None:
        op_id = _next_operation_id(context.campaign)
        target_descriptor_raw = order.parameters.get("target_descriptor")
        if target_descriptor_raw is None:
            target_descriptor: dict[str, object] = {}
        elif isinstance(target_descriptor_raw, dict):
            target_descriptor = cast(dict[str, object], target_descriptor_raw)
        else:
            return _failure("target_descriptor must be a mapping")

        operation_type_raw = order.parameters.get(
            "operation_type", OperationType.INTELLIGENCE.value
        )
        try:
            operation_type = OperationType(operation_type_raw)
        except ValueError:
            operation_type = OperationType.INTELLIGENCE

        territory_type = str(order.parameters.get("territory_type", "friendly"))
        try:
            difficulty_modifier = int(order.parameters.get("difficulty_modifier", 0))
        except (TypeError, ValueError):
            return _failure("difficulty_modifier must be an int")

        loot_cost = int(
            order.parameters.get("loot_cost", context.rules.operations.loot_cost_default)
        )
        operation = Operation(
            id=op_id,
            commander_id=order.commander_id,
            operation_type=operation_type,
            target_descriptor=target_descriptor,
            loot_cost=loot_cost,
            complexity=str(order.parameters.get("complexity", "standard")),
            success_chance=0.0,
            difficulty_modifier=difficulty_modifier,
            territory_type=territory_type,
            result=None,
        )
        context.campaign.operations[operation.id] = operation

    outcome = operations.resolve_operation(context.campaign, operation, rules=context.rules)
    return OrderExecutionResult(OrderStatus.COMPLETED, outcome.detail)


def _handle_harry(context: OrderContext, order: Order, army: Army | None) -> OrderExecutionResult:
    try:
        setup = _prepare_harrying_setup(context, order, army)
    except ValueError as exc:
        return _failure(str(exc))

    try:
        outcome = harrying.resolve_harrying(
            context.campaign,
            setup.attacker,
            setup.target,
            setup.detachments,
            options=harrying.HarryingOptions(
                objective=setup.objective,
                rules=context.rules,
            ),
        )
    except ValueError as exc:
        return _failure(str(exc))

    events: list[dict[str, object]] = [
        {
            "type": "harry",
            "success": outcome.success,
            "target_army_id": setup.target_id,
            "objective": setup.objective,
            "roll": outcome.roll,
            "modifier": outcome.modifier,
            "inflicted_casualties": outcome.inflicted_casualties,
            "attacker_losses": outcome.attacker_losses,
            "supplies_burned": outcome.supplies_burned,
            "supplies_stolen": outcome.supplies_stolen,
            "loot_stolen": outcome.loot_stolen,
        }
    ]

    status = OrderStatus.COMPLETED if outcome.success else OrderStatus.FAILED
    return OrderExecutionResult(status, outcome.detail, events)


@dataclass(slots=True)
class HarryingSetup:
    """Validated inputs required to execute a harry order."""

    attacker: Army
    target: Army
    target_id: int
    detachments: list[Detachment]
    objective: str


def _prepare_harrying_setup(
    context: OrderContext,
    order: Order,
    army: Army | None,
) -> HarryingSetup:
    if army is None:
        raise ValueError("harry order requires an army")

    det_ids_raw = order.parameters.get("detachment_ids")
    if not isinstance(det_ids_raw, list) or not det_ids_raw:
        raise ValueError("harry order requires detachment_ids")

    try:
        det_ids = {int(value) for value in det_ids_raw}
    except (TypeError, ValueError) as exc:
        raise ValueError("detachment_ids must be integers") from exc

    det_map = {int(det.id): det for det in army.detachments}
    selected = [det_map[det_id] for det_id in det_ids if det_id in det_map]
    if not selected:
        raise ValueError("no matching detachments for harrying")

    target_raw = order.parameters.get("target_army_id")
    try:
        target_id = int(target_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("harry order requires target_army_id") from exc

    target = context.campaign.armies.get(target_id)
    if target is None:
        raise ValueError("target army not found")

    objective = str(order.parameters.get("objective", "kill")).lower()

    return HarryingSetup(
        attacker=army,
        target=target,
        target_id=target_id,
        detachments=selected,
        objective=objective,
    )


_ORDER_HANDLERS: dict[str, OrderHandler] = {
    "move": _handle_move,
    "rest": _handle_rest,
    "forage": _handle_forage,
    "torch": _handle_torch,
    "supply_transfer": _handle_supply_transfer,
    "besiege": _handle_besiege,
    "assault": _handle_assault,
    "embark": _handle_embark,
    "disembark": _handle_disembark,
    "naval_move": _handle_naval_move,
    "send_message": _handle_send_message,
    "launch_operation": _handle_launch_operation,
    "raise_army": _handle_raise_army,
    "harry": _handle_harry,
}


def _failure(detail: str) -> OrderExecutionResult:
    return OrderExecutionResult(OrderStatus.FAILED, detail)


def _build_movement_legs(army: Army, legs_raw: list[dict[str, object]]) -> list[MovementLeg]:
    legs: list[MovementLeg] = []
    current_from = army.current_hex_id
    for index, payload in enumerate(legs_raw, start=1):
        try:
            to_hex = HexID(int(payload["to_hex_id"]))
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - validation
            raise OrderExecutionError("movement leg missing to_hex_id") from exc
        try:
            distance = float(payload.get("distance_miles", 0))
        except (TypeError, ValueError) as exc:
            raise OrderExecutionError("movement leg requires distance_miles") from exc
        if distance <= 0:
            raise OrderExecutionError("movement leg requires positive distance")
        on_road = bool(payload.get("on_road", True))
        has_ford = bool(payload.get("has_river_ford", False))
        is_night = bool(payload.get("is_night", False))
        has_fork = bool(payload.get("has_fork", False))
        alternate_hex = payload.get("alternate_hex_id")
        if has_fork and alternate_hex is None:
            raise OrderExecutionError("movement leg with fork requires alternate_hex_id")
        alternate_hex_id = None
        if alternate_hex is not None:
            try:
                alternate_hex_id = HexID(int(alternate_hex))
            except (TypeError, ValueError) as exc:
                raise OrderExecutionError("alternate_hex_id must be an int") from exc
        legs.append(
            MovementLeg(
                id=MovementLegID(index),
                from_hex_id=current_from,
                to_hex_id=to_hex,
                distance_miles=distance,
                on_road=on_road,
                has_river_ford=has_ford,
                is_night=is_night,
                has_fork=has_fork,
                alternate_hex_id=alternate_hex_id,
            )
        )
        current_from = to_hex
    return legs


def _hex_id_list(values: object) -> list[HexID]:
    if not isinstance(values, list):
        return []
    result: list[HexID] = []
    for value in values:
        try:
            result.append(HexID(int(value)))
        except (TypeError, ValueError):
            continue
    return result


def _prepare_movement_plan(
    context: OrderContext,
    army: Army,
    order: Order,
) -> MovementPlan:
    legs_raw = order.parameters.get("legs")
    if not isinstance(legs_raw, list) or not legs_raw:
        raise OrderExecutionError("movement order missing legs")
    legs_payload = cast(list[dict[str, object]], legs_raw)

    movement_type_name = order.parameters.get("movement_type", MovementType.STANDARD.value)
    try:
        movement_type = MovementType(movement_type_name)
    except ValueError as exc:
        raise OrderExecutionError(f"invalid movement type: {movement_type_name}") from exc

    weather_modifier = int(order.parameters.get("weather_modifier", 0))
    legs = _build_movement_legs(army, legs_payload)
    validation = movement.validate_movement_order(
        context.campaign.unit_types,
        army,
        off_road_legs=[not leg.on_road for leg in legs],
        has_river_fords=[leg.has_river_ford for leg in legs],
        is_night=movement_type == MovementType.NIGHT or any(leg.is_night for leg in legs),
    )
    if not validation.valid:
        raise OrderExecutionError(validation.error or "movement validation failed")

    commander = context.campaign.commanders.get(army.commander_id)
    traits = commander.traits if commander else []

    total_fraction = 0.0
    travelled: list[MovementLeg] = []
    final_hex = army.current_hex_id
    diverted = False
    diversion_detail: str | None = None

    for index, leg in enumerate(legs, start=1):
        leg_type = MovementType.NIGHT if leg.is_night else movement_type
        options = movement.MovementOptions(
            on_road=leg.on_road,
            traits=traits,
            weather_modifier=weather_modifier,
            rules=context.rules,
        )
        allowance = movement.calculate_daily_movement_miles(
            context.campaign.unit_types,
            army,
            leg_type,
            options,
        )
        if allowance <= 0:
            raise OrderExecutionError("movement allowance is zero for a leg")
        total_fraction += leg.distance_miles / allowance
        travelled.append(leg)
        final_hex = leg.to_hex_id

        if (movement_type == MovementType.NIGHT or leg.is_night) and leg.has_fork and not diverted:
            seed = f"night-fork:{int(order.id)}:{context.campaign.current_day}:{index}"
            if movement.should_take_wrong_fork(seed, rules=context.rules):
                if leg.alternate_hex_id is None:
                    raise OrderExecutionError("night fork requires alternate_hex_id")
                final_hex = leg.alternate_hex_id
                diverted = True
                diversion_detail = f"took wrong fork on leg {index}"
                break

    if total_fraction > 1.0:
        raise OrderExecutionError("movement exceeds daily allowance")

    return MovementPlan(
        movement_type=movement_type,
        legs=travelled,
        total_fraction=total_fraction,
        final_hex=final_hex,
        diverted=diverted,
        diversion_detail=diversion_detail,
    )


def _prepare_assault_context(
    context: OrderContext,
    order: Order,
) -> tuple[Stronghold, Army, Siege | None, battle.BattleOptions]:
    stronghold_id_raw = order.parameters.get("stronghold_id")
    try:
        stronghold_id = StrongholdID(int(stronghold_id_raw))
    except (TypeError, ValueError) as exc:
        raise OrderExecutionError("assault order missing stronghold_id") from exc

    stronghold = context.campaign.strongholds.get(stronghold_id)
    if stronghold is None:
        raise OrderExecutionError("stronghold not found")

    if stronghold.garrison_army_id is None:
        raise OrderExecutionError("stronghold has no garrison army")

    defender_army = context.campaign.armies.get(stronghold.garrison_army_id)
    if defender_army is None:
        raise OrderExecutionError("stronghold has no garrison army")

    siege = _find_siege_by_stronghold(context.campaign, stronghold_id)
    defender_bonus = stronghold.defensive_bonus
    engines = siege.siege_engines_count if siege else 0
    defender_bonus = max(0, defender_bonus - engines)

    try:
        attacker_fixed = _maybe_int(
            order.parameters.get("attacker_fixed_roll"), "attacker_fixed_roll must be an int"
        )
        defender_fixed = _maybe_int(
            order.parameters.get("defender_fixed_roll"), "defender_fixed_roll must be an int"
        )
        attacker_modifier = int(order.parameters.get("attacker_modifier", 0))
        defender_modifier = int(order.parameters.get("defender_modifier", 0))
    except OrderExecutionError:
        raise
    except (TypeError, ValueError) as exc:
        raise OrderExecutionError(str(exc)) from exc

    attacker_fixed_map = None
    if attacker_fixed is not None and order.army_id is not None:
        attacker_fixed_map = {order.army_id: attacker_fixed}

    defender_fixed_map = None
    if defender_fixed is not None:
        defender_fixed_map = {defender_army.id: defender_fixed}

    options = battle.BattleOptions(
        attacker_modifier=-1 + attacker_modifier,
        defender_modifier=defender_bonus + defender_modifier,
        attacker_fixed_rolls=attacker_fixed_map,
        defender_fixed_rolls=defender_fixed_map,
    )

    return stronghold, defender_army, siege, options


def _find_siege_by_stronghold(campaign: Campaign, stronghold_id: StrongholdID) -> Siege | None:
    for siege in campaign.sieges.values():
        if siege.stronghold_id == stronghold_id:
            return siege
    return None


def _next_siege_id(campaign: Campaign) -> SiegeID:
    if not campaign.sieges:
        return SiegeID(1)
    return SiegeID(max(int(siege_id) for siege_id in campaign.sieges) + 1)


def _apply_additional_losses(army: Army, percentage: float) -> None:
    for det in army.detachments:
        det.soldiers = max(1, int(det.soldiers * (1 - percentage)))
    army.supplies_current = int(army.supplies_current * (1 - percentage))


def _maybe_int(value: object, error: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OrderExecutionError(error) from exc


def _next_message_id(campaign: Campaign) -> MessageID:
    if not campaign.messages:
        return MessageID(1)
    return MessageID(max(int(message_id) for message_id in campaign.messages) + 1)


def _next_operation_id(campaign: Campaign) -> OperationID:
    if not campaign.operations:
        return OperationID(1)
    return OperationID(max(int(op_id) for op_id in campaign.operations) + 1)
