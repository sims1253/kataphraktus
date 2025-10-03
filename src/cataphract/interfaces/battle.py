"""Battle Service Protocol Interface.

This module defines the protocol (interface) for battle-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.domain.battle_data import BattleModifierParameters, BattleParameters
from cataphract.models.battle import Battle


class IBattleService(Protocol):
    """Protocol defining the interface for battle resolution operations.

    This protocol defines the contract for services that handle battle resolution,
    modifier calculations, and combat mechanics in the Cataphract game system.
    """

    def resolve_battle(self, parameters: BattleParameters) -> Battle:
        """Resolve a battle between two or more armies following Cataphract rules.

        Args:
            parameters: BattleParameters containing all battle information

        Returns:
            Battle model with resolution results
        """
        ...

    def calculate_battle_modifier(self, params: BattleModifierParameters) -> int:
        """Calculate battle modifiers for an army based on various factors.

        Args:
            params: BattleModifierParameters containing all necessary information

        Returns:
            Total battle modifier
        """
        ...
