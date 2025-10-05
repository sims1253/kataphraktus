"""Unit tests for messaging rules."""

from __future__ import annotations

from datetime import UTC, datetime

from cataphract.domain import messaging
from cataphract.domain import models as dm
from cataphract.domain.enums import DayPart, Season
from cataphract.domain.rules_config import MessagingRules, RulesConfig


def _campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Test",
        start_date=datetime(1325, 3, 1, tzinfo=UTC).date(),
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
    )
    destination = dm.Hex(
        id=dm.HexID(2),
        campaign_id=campaign.id,
        q=1,
        r=0,
        terrain="flatland",
        settlement=60,
    )
    campaign.map.hexes[origin.id] = origin
    campaign.map.hexes[destination.id] = destination
    sender = dm.Commander(
        id=dm.CommanderID(1),
        campaign_id=campaign.id,
        name="Sender",
        faction_id=dm.FactionID(1),
        age=30,
        current_hex_id=origin.id,
    )
    recipient = dm.Commander(
        id=dm.CommanderID(2),
        campaign_id=campaign.id,
        name="Recipient",
        faction_id=dm.FactionID(1),
        age=32,
        current_hex_id=destination.id,
    )
    campaign.commanders[sender.id] = sender
    campaign.commanders[recipient.id] = recipient
    return campaign


def _message(
    message_id: int,
    sender: dm.CommanderID,
    recipient: dm.CommanderID,
    territory: str,
) -> dm.Message:
    return dm.Message(
        id=dm.MessageID(message_id),
        campaign_id=dm.CampaignID(1),
        sender_id=sender,
        recipient_id=recipient,
        content="Test",
        sent_at=datetime(1325, 3, 1, tzinfo=UTC),
        delivered_at=None,
        travel_time_days=0.0,
        territory_type=territory,
        status="pending",
        legs=[],
        days_remaining=0.0,
        failure_reason=None,
    )


def test_dispatch_and_deliver_message_success():
    campaign = _campaign()
    rules = RulesConfig(
        messaging=MessagingRules(
            friendly_miles_per_day=48,
            neutral_miles_per_day=48,
            hostile_miles_per_day=36,
            friendly_success_numerator=20,
            friendly_success_denominator=20,
            hostile_success_numerator=5,
            hostile_success_denominator=6,
        )
    )

    message = _message(1, dm.CommanderID(1), dm.CommanderID(2), "friendly")
    result = messaging.dispatch_message(campaign, message, rules=rules)

    assert result.success
    assert message.status == "in_transit"
    assert message.travel_time_days > 0
    assert messaging.pending_messages_for_commander(campaign, dm.CommanderID(2)) == [message]

    # Advance enough to deliver
    while message.status == "in_transit":
        messaging.advance_messages(campaign, rules=rules, day_fraction=1.0)

    assert message.status == "delivered"
    assert messaging.pending_messages_for_commander(campaign, dm.CommanderID(2)) == []


def test_dispatch_failure_for_unknown_hex():
    campaign = _campaign()
    message = _message(2, dm.CommanderID(1), dm.CommanderID(2), "friendly")

    result = messaging.dispatch_message(campaign, message, from_hex=999, to_hex=None)

    assert not result.success
    assert "origin or destination" in result.detail
    assert message.id not in campaign.messages


def test_hostile_message_interception():
    campaign = _campaign()
    rules = RulesConfig(
        messaging=MessagingRules(
            friendly_miles_per_day=48,
            neutral_miles_per_day=48,
            hostile_miles_per_day=36,
            friendly_success_numerator=20,
            friendly_success_denominator=20,
            hostile_success_numerator=0,
            hostile_success_denominator=6,
        )
    )

    message = _message(3, dm.CommanderID(1), dm.CommanderID(2), "hostile")
    dispatch = messaging.dispatch_message(campaign, message, rules=rules)
    assert dispatch.success

    messaging.advance_messages(campaign, rules=rules, day_fraction=1.0)
    assert message.status == "failed"
    assert message.failure_reason == "intercepted"
