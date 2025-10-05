"""Messaging and courier rules."""

from __future__ import annotations

from dataclasses import dataclass

from cataphract.domain.models import Campaign, CommanderID, Message, MessageID
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.hex_math import HexCoord, hex_distance
from cataphract.utils.rng import roll_dice

DAY_PARTS_PER_DAY = 4
HEX_MILES = 6


@dataclass(slots=True)
class MessageDispatchResult:
    """Outcome of attempting to dispatch a message."""

    success: bool
    detail: str
    message_id: MessageID | None = None


speed_lookup = {
    "friendly": lambda rules: rules.messaging.friendly_miles_per_day,
    "neutral": lambda rules: rules.messaging.neutral_miles_per_day,
    "hostile": lambda rules: rules.messaging.hostile_miles_per_day,
}


success_lookup = {
    "friendly": lambda rules: (
        rules.messaging.friendly_success_numerator,
        rules.messaging.friendly_success_denominator,
        "1d20",
    ),
    "neutral": lambda rules: (
        rules.messaging.friendly_success_numerator,
        rules.messaging.friendly_success_denominator,
        "1d20",
    ),
    "hostile": lambda rules: (
        rules.messaging.hostile_success_numerator,
        rules.messaging.hostile_success_denominator,
        "1d6",
    ),
}


def dispatch_message(
    campaign: Campaign,
    message: Message,
    *,
    rules: RulesConfig = DEFAULT_RULES,
    from_hex: int | None = None,
    to_hex: int | None = None,
) -> MessageDispatchResult:
    """Queue a message for delivery and compute its travel time."""

    territory = message.territory_type.lower()
    if territory not in speed_lookup:
        return MessageDispatchResult(False, f"unknown territory: {territory}")

    if from_hex is None:
        sender = campaign.commanders.get(message.sender_id)
        from_hex = sender.current_hex_id if sender else None
    if to_hex is None:
        recipient = campaign.commanders.get(message.recipient_id)
        to_hex = recipient.current_hex_id if recipient else None

    if from_hex is None or to_hex is None:
        return MessageDispatchResult(False, "sender or recipient location unknown")

    origin_hex = campaign.map.hexes.get(from_hex) if from_hex is not None else None
    destination_hex = campaign.map.hexes.get(to_hex) if to_hex is not None else None
    if origin_hex is None or destination_hex is None:
        return MessageDispatchResult(False, "origin or destination hex missing")

    origin_coord = _to_coord(origin_hex)
    destination_coord = _to_coord(destination_hex)
    distance_hexes = max(1, hex_distance(origin_coord, destination_coord))
    speed = speed_lookup[territory](rules)
    miles = distance_hexes * HEX_MILES
    travel_days = max(1.0, miles / speed)

    message.travel_time_days = travel_days
    message.days_remaining = travel_days
    message.status = "in_transit"
    campaign.messages[message.id] = message

    return MessageDispatchResult(True, f"message dispatched: {travel_days:.2f} days", message.id)


def advance_messages(
    campaign: Campaign,
    *,
    rules: RulesConfig = DEFAULT_RULES,
    day_fraction: float = 1 / DAY_PARTS_PER_DAY,
) -> None:
    """Progress in-transit messages and resolve deliveries."""

    for message in campaign.messages.values():
        if message.status != "in_transit":
            continue

        message.days_remaining = max(0.0, message.days_remaining - day_fraction)
        if message.days_remaining > 0:
            continue

        numerator, denominator, _die = success_lookup[message.territory_type.lower()](rules)
        roll = roll_dice(f"message:{int(message.id)}", f"1d{denominator}")["total"]
        success = roll <= numerator
        if success:
            message.status = "delivered"
            message.delivered_at = message.delivered_at or message.sent_at
            message.failure_reason = None
        else:
            message.status = "failed"
            message.failure_reason = "intercepted"


def pending_messages_for_commander(
    campaign: Campaign,
    commander_id: CommanderID,
) -> list[Message]:
    """Return messages destined for the commander that are still in flight."""

    return [
        msg
        for msg in campaign.messages.values()
        if msg.recipient_id == commander_id and msg.status == "in_transit"
    ]


def _to_coord(hex_obj) -> HexCoord:
    return HexCoord(q=hex_obj.q, r=hex_obj.r)
