"""Service layer for Cataphract game logic.

This module provides the service layer implementation for the Cataphract wargame.

Architecture:
    - ArmyService: Army lifecycle, raising, disbanding, detachment management
    - BattleService: Combat resolution, battle outcomes
    - HarryingService: Harrying mechanics, detachment raiding
    - MoraleService: Morale checks, consequences, army routing
    - MovementService: Army movement, marching, river fording
    - SiegeService: Siege mechanics, assaults, stronghold capture
    - SupplyService: Supply logistics, foraging, torching
    - VisibilityService: Fog of war, scouting, visibility calculations

Usage:
    from cataphract.services.supply_service import SupplyService
    from cataphract.services.visibility_service import VisibilityService

    visibility = VisibilityService(session)
    supply = SupplyService(session, visibility)
    result = supply.forage(params)

Testing:
    from cataphract.services.supply_service import SupplyService

    class FakeVisibility:
        def get_visible_armies(self, commander, **kwargs):
            return [test_army]

    service = SupplyService(session, FakeVisibility())
    result = service.forage(params)
"""

from cataphract.services.battle_service import BattleService
from cataphract.services.harrying_service import HarryingService
from cataphract.services.morale_service import MoraleService
from cataphract.services.movement_service import MovementService
from cataphract.services.siege_service import SiegeService
from cataphract.services.supply_service import SupplyService
from cataphract.services.tick_service import advance_tick, update_weather
from cataphract.services.visibility_service import VisibilityService

__all__ = [
    "BattleService",
    "HarryingService",
    "MoraleService",
    "MovementService",
    "SiegeService",
    "SupplyService",
    "VisibilityService",
    "advance_tick",
    "update_weather",
]
