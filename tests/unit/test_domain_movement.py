"""Unit tests for movement rules."""

from __future__ import annotations

from cataphract.domain import enums as de
from cataphract.domain import models as dm
from cataphract.domain import movement


def _unit_types() -> dict[dm.UnitTypeID, dm.UnitType]:
    return {
        dm.UnitTypeID(1): dm.UnitType(
            id=dm.UnitTypeID(1),
            name="infantry",
            category="infantry",
            battle_multiplier=1.0,
            supply_cost_per_day=1,
            can_travel_offroad=True,
        ),
        dm.UnitTypeID(2): dm.UnitType(
            id=dm.UnitTypeID(2),
            name="cavalry",
            category="cavalry",
            battle_multiplier=2.0,
            supply_cost_per_day=10,
            can_travel_offroad=True,
            special_abilities={"acts_as_cavalry_for_foraging": True},
        ),
    }


def _army(cavalry_only: bool = False) -> dm.Army:
    detachments = [
        dm.Detachment(
            id=dm.DetachmentID(1),
            unit_type_id=dm.UnitTypeID(2 if cavalry_only else 1),
            soldiers=800,
            wagons=0,
        ),
    ]
    if not cavalry_only:
        detachments.append(
            dm.Detachment(
                id=dm.DetachmentID(2),
                unit_type_id=dm.UnitTypeID(2),
                soldiers=200,
            )
        )

    return dm.Army(
        id=dm.ArmyID(1),
        campaign_id=dm.CampaignID(1),
        commander_id=dm.CommanderID(1),
        current_hex_id=dm.HexID(1),
        detachments=detachments,
        status=de.ArmyStatus.IDLE,
        status_effects={},
        noncombatant_count=250,
    )


def test_standard_movement_on_and_off_road():
    army = _army()
    units = _unit_types()
    miles_road = movement.calculate_daily_movement_miles(
        units,
        army,
        de.MovementType.STANDARD,
        movement.MovementOptions(on_road=True),
    )
    miles_offroad = movement.calculate_daily_movement_miles(
        units,
        army,
        de.MovementType.STANDARD,
        movement.MovementOptions(on_road=False),
    )

    assert miles_road == 12
    assert miles_offroad == 6


def test_forced_march_and_cavalry_bonus():
    units = _unit_types()
    army = _army()
    forced = movement.calculate_daily_movement_miles(
        units,
        army,
        de.MovementType.FORCED,
        movement.MovementOptions(on_road=True),
    )
    cavalry = _army(cavalry_only=True)
    cavalry.noncombatant_count = 0
    double = movement.calculate_daily_movement_miles(
        units,
        cavalry,
        de.MovementType.FORCED,
        movement.MovementOptions(on_road=True),
    )

    assert forced == 18
    assert double == 36


def test_weather_and_column_cap():
    units = _unit_types()
    army = _army()
    army.detachments[0].wagons = 400  # exaggerate column length
    capped = movement.calculate_daily_movement_miles(
        units,
        army,
        de.MovementType.STANDARD,
        movement.MovementOptions(on_road=True, weather_modifier=-2),
    )
    assert capped == 6  # capped speed


def test_fording_delay_and_validation():
    units = _unit_types()
    army = _army()
    delay = movement.calculate_fording_delay(units, army)
    assert delay > 0

    validation = movement.validate_movement_order(
        units,
        army,
        off_road_legs=[False],
        has_river_fords=[True],
        is_night=False,
    )
    assert validation.valid

    bad = movement.validate_movement_order(
        units,
        army,
        off_road_legs=[True],
        has_river_fords=[False],
        is_night=True,
    )
    assert not bad.valid
