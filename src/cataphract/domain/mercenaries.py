"""Mercenary upkeep and contract management."""

from __future__ import annotations

from cataphract.domain import morale
from cataphract.domain.models import Campaign, MercenaryContract
from cataphract.domain.rules_config import DEFAULT_RULES, RulesConfig
from cataphract.utils.rng import roll_dice


def process_daily_upkeep(campaign: Campaign, *, rules: RulesConfig = DEFAULT_RULES) -> None:
    """Charge upkeep for all active mercenary contracts."""

    for contract in campaign.mercenary_contracts.values():
        if contract.status not in {"active", "unpaid"}:
            continue
        if contract.army_id is None:
            continue
        army = campaign.armies.get(contract.army_id)
        if army is None:
            continue

        days_due = campaign.current_day - contract.last_upkeep_day
        if days_due <= 0:
            continue

        daily_rate = _daily_upkeep_cost(campaign, contract, rules)
        total_due = daily_rate * days_due

        if army.loot_carried >= total_due:
            army.loot_carried -= total_due
            contract.last_upkeep_day = campaign.current_day
            contract.days_unpaid = 0
            if contract.status == "unpaid":
                contract.status = "active"
            continue

        # Unpaid upkeep
        contract.days_unpaid += days_due
        contract.status = "unpaid"
        contract.last_upkeep_day = campaign.current_day
        morale.adjust_morale(army, -rules.mercenaries.morale_penalty_unpaid)

        if contract.days_unpaid > rules.mercenaries.grace_days_without_pay:
            _maybe_trigger_desertion(campaign, contract, army, rules)


def _daily_upkeep_cost(
    campaign: Campaign,
    contract: MercenaryContract,
    rules: RulesConfig,
) -> int:
    army = campaign.armies.get(contract.army_id)
    if army is None:
        return 0

    infantry = 0
    cavalry = 0
    for det in army.detachments:
        unit = campaign.unit_types.get(det.unit_type_id)
        category = getattr(unit, "category", "infantry") if unit else "infantry"
        if category == "cavalry":
            cavalry += det.soldiers
        else:
            infantry += det.soldiers

    infantry_rate = contract.negotiated_rates.get("infantry") if contract.negotiated_rates else None
    cavalry_rate = contract.negotiated_rates.get("cavalry") if contract.negotiated_rates else None

    infantry_rate = infantry_rate or rules.mercenaries.infantry_upkeep_per_day
    cavalry_rate = cavalry_rate or rules.mercenaries.cavalry_upkeep_per_day

    return infantry * infantry_rate + cavalry * cavalry_rate


def _maybe_trigger_desertion(
    campaign: Campaign,
    contract: MercenaryContract,
    army,
    rules: RulesConfig,
) -> None:
    roll = roll_dice(
        f"mercenary-desertion:{int(contract.id)}",
        f"1d{rules.mercenaries.desertion_chance_denominator}",
    )["total"]
    success = roll <= rules.mercenaries.desertion_chance_numerator
    if not success:
        return

    contract.status = "terminated"
    army.status_effects = army.status_effects or {}
    army.status_effects["mercenaries_deserted"] = {
        "contract_id": int(contract.id),
        "day": campaign.current_day,
    }
    morale.adjust_morale(army, -rules.mercenaries.morale_penalty_unpaid)
