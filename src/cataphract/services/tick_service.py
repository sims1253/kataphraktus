"""Time & Tick Management Service for the Cataphract game.

This service manages game time progression, including:
- Advancing dayparts and days
- Processing tick sequences (messages, orders, battles)
- Weather generation and updates
- Supply consumption and weekly counter resets
- Event generation for all significant actions

See ARCHITECTURE.md (lines 307-336) and RULES_IMPLEMENTATION_NOTES.md (section 3)
for detailed tick ordering and time management rules.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cataphract.models import Army, Battle, Event, Game, Message, Order, Weather
from cataphract.services.supply_service import SupplyService
from cataphract.services.visibility_service import VisibilityService
from cataphract.utils import rng

# Constants for sick/exhausted calculations
FORCED_MARCH_FATIGUE_DAYS = 3
WEATHER_EXPOSURE_DAYS = 2
STARVATION_DISSOLUTION_DAYS = 14


def advance_tick(game_id: int, session: Session) -> dict[str, Any]:
    """Advance game by one daypart, processing all time-based events.

    Increments current_day_part: morning → midday → evening → night → morning (next day).
    Processes tick sequence per RULES_IMPLEMENTATION_NOTES.md section 3.

    Args:
        game_id: Game ID to advance
        session: Database session

    Returns:
        Dictionary with tick results (game_id, days, parts, counts)
    """
    game = session.get(Game, game_id)
    if not game:
        raise ValueError(f"Game {game_id} not found")

    prev_day, prev_part = game.current_day, game.current_day_part

    # Increment daypart
    part_order = ["morning", "midday", "evening", "night"]
    next_idx = (part_order.index(game.current_day_part) + 1) % 4
    if next_idx == 0:
        game.current_day += 1
    game.current_day_part = part_order[next_idx]

    # Phase 1: Start-of-Day Flags (Morning only)
    if game.current_day_part == "morning":
        _process_start_of_day_flags(game_id, game.current_day, session)
        update_weather(game_id, game.current_day, session)
        if game.current_day % 7 == 0 and game.current_day > 0:
            _reset_weekly_counters(game_id, session)

    # Phase 2: Deliver Messages
    msg_count = _process_message_deliveries(
        game_id, game.current_day, game.current_day_part, session
    )

    # Phase 3: Execute Orders
    ord_count = _process_scheduled_orders(game_id, game.current_day, game.current_day_part, session)

    # Phase 4: Resolve Battles (uses start-of-day flags)
    bat_count = _resolve_battles(game_id, game.current_day, game.current_day_part, session)

    # Phase 5: End-of-Day Processing (at morning for previous day)
    if game.current_day_part == "morning":
        visibility = VisibilityService(session)
        supply = SupplyService(session, visibility)
        _consume_supplies(game_id, game.current_day - 1, session, supply)

    session.commit()

    evt_count = len(
        session.execute(
            select(Event).where(
                Event.game_id == game_id,
                Event.game_day == game.current_day,
                Event.game_part == game.current_day_part,
            )
        )
        .scalars()
        .all()
    )

    return {
        "game_id": game_id,
        "previous_day": prev_day,
        "previous_part": prev_part,
        "current_day": game.current_day,
        "current_part": game.current_day_part,
        "messages_delivered": msg_count,
        "orders_executed": ord_count,
        "battles_resolved": bat_count,
        "events_generated": evt_count,
    }


def update_weather(game_id: int, day: int, session: Session) -> Weather:
    """Update weather for a new day using deterministic RNG.

    Args:
        game_id: Game ID
        day: Game day to generate weather for
        session: Database session

    Returns:
        Weather object for the day
    """
    game = session.get(Game, game_id)
    if not game:
        raise ValueError(f"Game {game_id} not found")

    seed = rng.generate_seed(game_id, day, "morning", "weather")
    probabilities = _get_weather_probabilities(game.season)

    # Roll for weather type
    roll = rng.random_int(seed, 1, 100)
    cumulative = 0
    weather_type = "clear"
    for wtype, prob in probabilities.items():
        cumulative += prob
        if roll["value"] <= cumulative:
            weather_type = wtype
            break

    effects = _get_weather_effects(weather_type)

    weather = Weather(game_id=game_id, game_day=day, weather_type=weather_type, effects=effects)
    session.add(weather)

    event = Event(
        game_id=game_id,
        game_day=day,
        game_part="morning",
        timestamp=datetime.now(UTC),
        event_type="weather_change",
        involved_entities={},
        description=f"Weather changed to {weather_type}",
        details={"weather_type": weather_type, "effects": effects},
        rand_source={"seed": seed, "roll": roll},
        visible_to=[],
    )
    session.add(event)

    return weather


def _process_start_of_day_flags(game_id: int, day: int, session: Session) -> None:
    """Set start-of-day flags (undersupplied, sick_or_exhausted) for all armies."""
    armies = session.execute(select(Army).where(Army.game_id == game_id)).scalars().all()

    for army in armies:
        if army.status_effects is None:
            army.status_effects = {}

        # Set undersupplied flag
        is_undersupplied = (army.supplies_current < army.daily_supply_consumption) or (
            army.days_without_supplies > 0
        )
        if is_undersupplied:
            army.status_effects["undersupplied"] = {
                "active": True,
                "until_day": day + 1,
            }
        else:
            army.status_effects.pop("undersupplied", None)

        # Set sick_or_exhausted flag
        sick_or_exhausted = _calculate_sick_or_exhausted(army, day, session)
        if sick_or_exhausted:
            army.status_effects["sick_or_exhausted"] = {
                "active": True,
                "reason": sick_or_exhausted["reason"],
                "until_day": day + 1,
            }
        else:
            army.status_effects.pop("sick_or_exhausted", None)


def _calculate_sick_or_exhausted(army: Army, day: int, session: Session) -> dict[str, Any] | None:
    """Determine if army is sick/exhausted per RULES_IMPLEMENTATION_NOTES.md section 2."""
    # 1. Check recent combat
    battles = (
        session.execute(
            select(Battle).where(Battle.game_id == army.game_id, Battle.game_day == day - 1)
        )
        .scalars()
        .all()
    )
    for battle in battles:
        if army.id in battle.attacker_side or army.id in battle.defender_side:
            return {"reason": "fought_battle_yesterday"}

    # 2. Check forced march fatigue
    if army.days_marched_this_week >= FORCED_MARCH_FATIGUE_DAYS and army.status == "forced_march":
        return {"reason": "forced_march_fatigue"}

    # 3-5. Check other conditions
    if army.days_without_supplies > 0:
        return {"reason": "starvation"}
    if army.supplies_current < army.daily_supply_consumption:
        return {"reason": "undersupplied"}
    if _get_consecutive_bad_weather_days(army.game_id, day, session) >= WEATHER_EXPOSURE_DAYS:
        return {"reason": "weather_exposure"}

    return None


def _get_consecutive_bad_weather_days(game_id: int, day: int, session: Session) -> int:
    """Get count of consecutive bad weather days leading up to today."""
    count = 0
    for check_day in range(day, max(0, day - 7), -1):
        weather = (
            session.execute(
                select(Weather).where(Weather.game_id == game_id, Weather.game_day == check_day)
            )
            .scalars()
            .first()
        )
        if weather and weather.weather_type in ["storm", "very_bad"]:
            count += 1
        else:
            break
    return count


def _process_message_deliveries(game_id: int, day: int, part: str, session: Session) -> int:
    """Process messages scheduled for delivery at this (day, part)."""
    messages = (
        session.execute(
            select(Message).where(Message.game_id == game_id, Message.status == "in_transit")
        )
        .scalars()
        .all()
    )

    delivered_count = 0
    for msg in messages:
        if "eta_day" in msg.route_legs and "eta_part" in msg.route_legs:
            eta_day, eta_part = msg.route_legs["eta_day"], msg.route_legs["eta_part"]
            if eta_day < day or (eta_day == day and _part_index(eta_part) <= _part_index(part)):
                msg.status = "delivered"
                msg.delivered_at_day = day
                msg.delivered_at_part = part
                msg.delivered_at_timestamp = datetime.now(UTC)

                event = Event(
                    game_id=game_id,
                    game_day=day,
                    game_part=part,
                    timestamp=datetime.now(UTC),
                    event_type="message_delivered",
                    involved_entities={
                        "sender_id": msg.sender_commander_id,
                        "recipient_id": msg.recipient_commander_id,
                        "message_id": msg.id,
                    },
                    description=f"Message delivered to commander {msg.recipient_commander_id}",
                    details={"message_content": msg.content},
                    rand_source=None,
                    visible_to=[msg.recipient_commander_id],
                )
                session.add(event)
                delivered_count += 1

    return delivered_count


def _process_scheduled_orders(game_id: int, day: int, part: str, session: Session) -> int:
    """Execute orders scheduled for this (day, part)."""
    orders = (
        session.execute(
            select(Order).where(
                Order.game_id == game_id,
                Order.status == "pending",
                Order.execute_at_day == day,
                Order.execute_at_part == part,
            )
        )
        .scalars()
        .all()
    )

    for order in orders:
        order.status = "executing"
        order.executed_at_day = day
        order.executed_at_part = part

    return len(orders)


def _resolve_battles(game_id: int, day: int, part: str, session: Session) -> int:
    """Resolve battles by checking for armies in same hex (simplified)."""
    armies = (
        session.execute(
            select(Army).where(
                Army.game_id == game_id, Army.status.in_(["marching", "idle", "forced_march"])
            )
        )
        .scalars()
        .all()
    )

    # Group armies by hex
    armies_by_hex: dict[int, list[Army]] = {}
    for army in armies:
        if army.current_hex_id not in armies_by_hex:
            armies_by_hex[army.current_hex_id] = []
        armies_by_hex[army.current_hex_id].append(army)

    battles_count = 0
    for hex_id, hex_armies in armies_by_hex.items():
        if len(hex_armies) > 1:
            event = Event(
                game_id=game_id,
                game_day=day,
                game_part=part,
                timestamp=datetime.now(UTC),
                event_type="battle",
                involved_entities={"armies": [a.id for a in hex_armies], "hex_id": hex_id},
                description=f"Potential battle at hex {hex_id}",
                details={"army_count": len(hex_armies)},
                rand_source=None,
                visible_to=[a.commander_id for a in hex_armies],
            )
            session.add(event)
            battles_count += 1

    return battles_count


def _consume_supplies(game_id: int, day: int, session: Session, supply) -> None:  # type: ignore[no-untyped-def]
    """Consume supplies for all armies at end of day (night)."""
    armies = session.execute(select(Army).where(Army.game_id == game_id)).scalars().all()

    for army in armies:
        result = supply.consume_supplies(army)

        # Generate events for starvation
        if result["army_status"] == "starving":
            session.add(
                Event(
                    game_id=game_id,
                    game_day=day + 1,
                    game_part="morning",
                    timestamp=datetime.now(UTC),
                    event_type="morale_check",
                    involved_entities={"army_id": army.id},
                    description=f"Army {army.id} suffering from lack of supplies",
                    details={
                        "days_without_supplies": result["starvation_days"],
                        "morale": army.morale_current,
                    },
                    rand_source=None,
                    visible_to=[army.commander_id],
                )
            )

        if result["army_status"] == "dissolved":
            session.add(
                Event(
                    game_id=game_id,
                    game_day=day + 1,
                    game_part="morning",
                    timestamp=datetime.now(UTC),
                    event_type="army_split",
                    involved_entities={"army_id": army.id},
                    description=f"Army {army.id} dissolved due to starvation",
                    details={"reason": "starvation", "days": STARVATION_DISSOLUTION_DAYS},
                    rand_source=None,
                    visible_to=[army.commander_id],
                )
            )

        # Increment march counter
        if army.status in ("marching", "forced_march", "night_march"):
            army.days_marched_this_week += 1


def _reset_weekly_counters(game_id: int, session: Session) -> None:
    """Reset weekly counters (days_marched_this_week) for all armies."""
    armies = session.execute(select(Army).where(Army.game_id == game_id)).scalars().all()
    for army in armies:
        army.days_marched_this_week = 0


def _get_weather_probabilities(season: str) -> dict[str, int]:
    """Get cumulative weather probabilities (0-100) for a season."""
    probs = {
        "spring": {"clear": 40, "rain": 30, "fog": 15, "storm": 10, "snow": 5},
        "summer": {"clear": 60, "rain": 20, "fog": 10, "storm": 5, "snow": 0, "very_bad": 5},
        "fall": {"clear": 35, "rain": 30, "fog": 20, "storm": 10, "snow": 5},
        "winter": {"clear": 25, "snow": 35, "storm": 20, "fog": 10, "very_bad": 10},
    }
    return probs.get(season, {"clear": 50, "rain": 20, "fog": 15, "storm": 10, "snow": 5})


def _get_weather_effects(weather_type: str) -> dict[str, Any]:
    """Get effects (scouting_mod, movement_mod, etc.) for a weather type."""
    effects_map = {
        "clear": {"scouting_mod": 0, "movement_mod": 0},
        "rain": {"scouting_mod": -1, "movement_mod": 0},
        "snow": {"scouting_mod": -1, "movement_mod": -1},
        "fog": {"scouting_mod": -1, "movement_mod": 0},
        "storm": {"scouting_mod": -2, "movement_mod": -1, "battle_mod": -1},
        "very_bad": {"scouting_mod": -2, "movement_mod": -2, "battle_mod": -1, "sick_risk": True},
    }
    return effects_map.get(weather_type, {"scouting_mod": 0, "movement_mod": 0})


def _part_index(part: str) -> int:
    """Get index of daypart for comparison (0-3)."""
    return ["morning", "midday", "evening", "night"].index(part)
