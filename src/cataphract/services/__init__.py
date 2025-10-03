"""Service layer for Cataphract game logic.

This module provides the service layer implementation for the Cataphract wargame.
All services use protocol-based dependency inversion for clean architecture:

- Services depend on Protocol interfaces (IVisibilityService, IBattleService, etc.)
- Use factory.py for production dependency wiring
- Inject protocol-based fakes for testing (avoid complex mocking)

Architecture:
    - ArmyService: Army lifecycle, raising, disbanding, detachment management
    - BattleService: Combat resolution, battle outcomes
    - HarryingService: Harrying mechanics, detachment raiding
    - MoraleService: Morale checks, consequences, army routing
    - MovementService: Army movement, marching, river fording
    - SiegeService: Siege mechanics, assaults, stronghold capture
    - SupplyService: Supply logistics, foraging, torching
    - VisibilityService: Fog of war, scouting, visibility calculations

Production Usage:
    from cataphract.factory import create_supply_service
    supply = create_supply_service(session)
    result = supply.forage(army, target_hexes)

Testing Usage:
    from cataphract.services.supply_service import SupplyService
    from cataphract.interfaces import IVisibilityService

    class FakeVisibility:
        def get_visible_armies(self, commander, **kwargs):
            return [test_army]

    service = SupplyService(session, FakeVisibility())
    result = service.forage(army, target_hexes)
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
