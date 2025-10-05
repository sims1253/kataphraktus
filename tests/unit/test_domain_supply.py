"""Unit tests for the new domain-centric supply subsystem."""

from __future__ import annotations

from datetime import date

from cataphract.domain import models as dm
from cataphract.domain.enums import ArmyStatus, DayPart, Season
from cataphract.domain.rules_config import DEFAULT_RULES
from cataphract.domain.supply import (
    ForageOutcome,
    SupplyOptions,
    SupplySnapshot,
    TorchOutcome,
    build_supply_snapshot,
    forage,
    torch,
)


def _mk_campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Test",
        start_date=date(1325, 3, 1),
        current_day=10,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )

    infantry = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="infantry",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
    )
    cavalry = dm.UnitType(
        id=dm.UnitTypeID(2),
        name="cavalry",
        category="cavalry",
        battle_multiplier=2.0,
        supply_cost_per_day=10,
        can_travel_offroad=True,
        special_abilities={"acts_as_cavalry_for_foraging": True},
    )
    campaign.unit_types = {
        dm.UnitTypeID(1): infantry,
        dm.UnitTypeID(2): cavalry,
    }

    campaign.commanders = {
        dm.CommanderID(1): dm.Commander(
            id=dm.CommanderID(1),
            campaign_id=campaign.id,
            name="Test Commander",
            faction_id=dm.FactionID(1),
            age=35,
            traits=[],
        )
    }

    # Hex map containing the army hex and two adjacent targets
    army_hex = dm.Hex(
        id=dm.HexID(1),
        campaign_id=campaign.id,
        q=0,
        r=0,
        terrain="flatland",
        settlement=40,
        controlling_faction_id=dm.FactionID(1),
    )
    forage_hex = dm.Hex(
        id=dm.HexID(2),
        campaign_id=campaign.id,
        q=1,
        r=0,
        terrain="flatland",
        settlement=60,
        controlling_faction_id=dm.FactionID(1),
    )
    distant_hex = dm.Hex(
        id=dm.HexID(3),
        campaign_id=campaign.id,
        q=5,
        r=0,
        terrain="flatland",
        settlement=60,
        controlling_faction_id=dm.FactionID(2),
    )
    campaign.map.hexes = {
        dm.HexID(1): army_hex,
        dm.HexID(2): forage_hex,
        dm.HexID(3): distant_hex,
    }

    return campaign


def _mk_army(campaign: dm.Campaign) -> dm.Army:
    infantry_det = dm.Detachment(
        id=dm.DetachmentID(1),
        unit_type_id=dm.UnitTypeID(1),
        soldiers=800,
        wagons=4,
    )
    cavalry_det = dm.Detachment(
        id=dm.DetachmentID(2),
        unit_type_id=dm.UnitTypeID(2),
        soldiers=200,
    )
    army = dm.Army(
        id=dm.ArmyID(1),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(1),
        current_hex_id=dm.HexID(1),
        detachments=[infantry_det, cavalry_det],
        status=ArmyStatus.IDLE,
    )
    campaign.armies[army.id] = army
    return army


class FixedRoller:
    """Deterministic die roller for revolt checks."""

    def __init__(self, value: int) -> None:
        self.value = value

    def __call__(self) -> int:  # pragma: no cover - simple helper
        return self.value


def test_build_supply_snapshot_basic():
    campaign = _mk_campaign()
    army = _mk_army(campaign)

    snapshot = build_supply_snapshot(campaign, army)

    assert isinstance(snapshot, SupplySnapshot)
    assert snapshot.total_soldiers == 1000
    assert snapshot.total_cavalry == 200
    assert snapshot.total_wagons == 4
    assert snapshot.noncombatants == int(1000 * DEFAULT_RULES.supply.base_noncombatant_ratio)
    assert snapshot.capacity > 0
    assert snapshot.consumption > 0
    assert snapshot.column_length_miles > 0


def test_forage_success_adds_supplies():
    campaign = _mk_campaign()
    army = _mk_army(campaign)
    army.supplies_capacity = 50_000
    army.supplies_current = 10_000

    result = forage(
        campaign,
        army,
        [dm.HexID(2)],
        SupplyOptions(weather="clear", roll_d6=FixedRoller(6)),
    )

    assert isinstance(result, ForageOutcome)
    assert result.success
    assert result.supplies_gained == 60 * DEFAULT_RULES.supply.foraging_multiplier
    assert dm.HexID(2) in result.foraged_hexes
    assert not result.revolt_triggered
    assert campaign.map.hexes[dm.HexID(2)].foraging_times_remaining == 4
    assert army.supplies_current == 10_000 + result.supplies_gained


def test_forage_out_of_range_fails():
    campaign = _mk_campaign()
    army = _mk_army(campaign)

    result = forage(
        campaign,
        army,
        [dm.HexID(3)],
        SupplyOptions(weather="clear", roll_d6=FixedRoller(6)),
    )

    assert not result.success
    assert result.supplies_gained == 0
    assert result.failed_hexes[0][0] == dm.HexID(3)


def test_torch_triggers_revolt_when_roll_low():
    campaign = _mk_campaign()
    army = _mk_army(campaign)

    result = torch(
        campaign,
        army,
        [dm.HexID(2)],
        SupplyOptions(roll_d6=FixedRoller(1)),
    )

    assert isinstance(result, TorchOutcome)
    assert result.success
    assert result.revolt_triggered
    assert campaign.map.hexes[dm.HexID(2)].is_torched
    assert campaign.map.hexes[dm.HexID(2)].foraging_times_remaining == 0


def test_torch_without_rng_never_triggers_revolt():
    campaign = _mk_campaign()
    army = _mk_army(campaign)

    result = torch(campaign, army, [dm.HexID(2)])

    assert result.success
    assert not result.revolt_triggered
