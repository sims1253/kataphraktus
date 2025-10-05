"""Unit tests for mercenary upkeep rules."""

from __future__ import annotations

from datetime import date

from cataphract.domain import mercenaries
from cataphract.domain import models as dm
from cataphract.domain.enums import ArmyStatus, DayPart, Season
from cataphract.domain.rules_config import MercenaryRules, RulesConfig


def _campaign() -> dm.Campaign:
    campaign = dm.Campaign(
        id=dm.CampaignID(1),
        name="Mercenary Test",
        start_date=date(1325, 3, 1),
        current_day=1,
        current_part=DayPart.MORNING,
        season=Season.SPRING,
        status="active",
    )
    unit_type = dm.UnitType(
        id=dm.UnitTypeID(1),
        name="infantry",
        category="infantry",
        battle_multiplier=1.0,
        supply_cost_per_day=1,
        can_travel_offroad=True,
    )
    campaign.unit_types[unit_type.id] = unit_type
    return campaign


def _army(campaign: dm.Campaign, army_id: int, loot: int) -> dm.Army:
    army = dm.Army(
        id=dm.ArmyID(army_id),
        campaign_id=campaign.id,
        commander_id=dm.CommanderID(army_id),
        current_hex_id=dm.HexID(1),
        detachments=[
            dm.Detachment(
                id=dm.DetachmentID(army_id),
                unit_type_id=dm.UnitTypeID(1),
                soldiers=400,
            )
        ],
        status=ArmyStatus.IDLE,
        supplies_current=500,
        supplies_capacity=10_000,
        loot_carried=loot,
        status_effects={},
    )
    campaign.armies[army.id] = army
    return army


def test_process_upkeep_paid():
    campaign = _campaign()
    army = _army(campaign, 1, loot=1_000)
    contract = dm.MercenaryContract(
        id=dm.MercenaryContractID(1),
        company_id=dm.MercenaryCompanyID(1),
        commander_id=army.commander_id,
        army_id=army.id,
        start_day=0,
        end_day=None,
        status="active",
        last_upkeep_day=0,
        negotiated_rates=None,
    )
    campaign.mercenary_contracts[contract.id] = contract

    rules = RulesConfig(
        mercenaries=MercenaryRules(
            infantry_upkeep_per_day=1,
            cavalry_upkeep_per_day=3,
            grace_days_without_pay=3,
            morale_penalty_unpaid=1,
            desertion_chance_numerator=1,
            desertion_chance_denominator=6,
        )
    )

    mercenaries.process_daily_upkeep(campaign, rules=rules)

    assert army.loot_carried == 600  # 400 infantry upkeep paid once
    assert contract.last_upkeep_day == campaign.current_day
    assert contract.days_unpaid == 0
    assert contract.status == "active"


def test_unpaid_contract_triggers_desertion():
    campaign = _campaign()
    campaign.current_day = 2
    army = _army(campaign, 2, loot=0)
    contract = dm.MercenaryContract(
        id=dm.MercenaryContractID(2),
        company_id=dm.MercenaryCompanyID(1),
        commander_id=army.commander_id,
        army_id=army.id,
        start_day=0,
        end_day=None,
        status="active",
        last_upkeep_day=1,
        negotiated_rates=None,
    )
    campaign.mercenary_contracts[contract.id] = contract

    rules = RulesConfig(
        mercenaries=MercenaryRules(
            infantry_upkeep_per_day=1,
            cavalry_upkeep_per_day=3,
            grace_days_without_pay=0,
            morale_penalty_unpaid=1,
            desertion_chance_numerator=6,
            desertion_chance_denominator=6,
        )
    )

    mercenaries.process_daily_upkeep(campaign, rules=rules)

    assert contract.status == "terminated"
    assert contract.days_unpaid > 0
    assert "mercenaries_deserted" in (army.status_effects or {})
