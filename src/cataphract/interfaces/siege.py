"""Siege Service Protocol Interface.

This module defines the protocol (interface) for siege-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.models import Army, Stronghold


class ISiegeService(Protocol):
    """Protocol defining the interface for siege and assault operations.

    This protocol defines the contract for services that handle sieges, assaults,
    and stronghold mechanics in the Cataphract game system.
    """

    def launch_assault(
        self, attacker_armies: list[Army], stronghold: Stronghold, battle_plan: str = ""
    ) -> dict:
        """Launch an assault on a stronghold.

        Args:
            attacker_armies: List of armies launching the assault
            stronghold: The stronghold being assaulted
            battle_plan: Battle plan description

        Returns:
            Dictionary with assault results including:
                - success: Whether the assault was launched
                - battle_result: Battle model with results
                - message: Status message
                - events: List of events
        """
        ...
