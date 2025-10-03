"""Protocol-based interfaces for Cataphract services.

This module exports all service protocol interfaces, providing a clear contract
for service implementations and enabling dependency injection and testing.
"""

from cataphract.interfaces.battle import IBattleService
from cataphract.interfaces.morale import IMoraleService
from cataphract.interfaces.movement import IMovementService
from cataphract.interfaces.siege import ISiegeService
from cataphract.interfaces.supply import ISupplyService
from cataphract.interfaces.visibility import IVisibilityService

__all__ = [
    "IBattleService",
    "IMoraleService",
    "IMovementService",
    "ISiegeService",
    "ISupplyService",
    "IVisibilityService",
]
