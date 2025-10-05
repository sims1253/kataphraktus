"""Unit tests for operation resolution rules."""

from __future__ import annotations

from datetime import date

from cataphract.domain import models as dm
from cataphract.domain import operations
from cataphract.domain.enums import DayPart, OperationOutcome, OperationType, Season
from cataphract.domain.rules_config import DEFAULT_RULES
from cataphract.utils import rng


def _campaign() -> dm.Campaign:
    return dm.Campaign(
        id=dm.CampaignID(1),
        name="Operations",
        start_date=date(1325, 3, 1),
        current_day=10,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )


def test_operation_success_matches_roll():
    campaign = _campaign()
    seed = "op-success"
    expected_roll = rng.roll_dice(seed, "2d6")["total"]

    operation = dm.Operation(
        id=dm.OperationID(1),
        commander_id=dm.CommanderID(1),
        operation_type=OperationType.INTELLIGENCE,
        target_descriptor={},
        loot_cost=100,
        complexity="standard",
        success_chance=0.0,
        difficulty_modifier=DEFAULT_RULES.operations.base_success_target - expected_roll,
        territory_type="friendly",
    )
    campaign.operations[operation.id] = operation

    result = operations.resolve_operation(campaign, operation, seed=seed)

    assert result.roll == expected_roll
    assert result.target == expected_roll
    assert operation.outcome == OperationOutcome.SUCCESS
    assert operation.result is not None
    assert operation.result["success"] is True


def test_operation_failure_when_target_exceeds_roll():
    campaign = _campaign()
    seed = "op-failure"
    roll = rng.roll_dice(seed, "2d6")["total"]

    operation = dm.Operation(
        id=dm.OperationID(2),
        commander_id=dm.CommanderID(2),
        operation_type=OperationType.ASSASSINATION,
        target_descriptor={},
        loot_cost=150,
        complexity="complex",
        success_chance=0.0,
        difficulty_modifier=DEFAULT_RULES.operations.base_success_target - roll - 1,
        territory_type="hostile",
    )
    campaign.operations[operation.id] = operation

    result = operations.resolve_operation(campaign, operation, seed=seed)

    assert result.roll == roll
    assert result.target > roll
    assert operation.outcome == OperationOutcome.FAILURE
    assert operation.result is not None
    assert operation.result["success"] is False
