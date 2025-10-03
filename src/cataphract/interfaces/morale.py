"""Morale Service Protocol Interface.

This module defines the protocol (interface) for morale-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.models import Army


class IMoraleService(Protocol):
    """Protocol defining the interface for morale-related operations.

    This protocol defines the contract for services that handle morale checks,
    consequences, routing, and morale updates in the Cataphract game system.
    """

    def check_morale(self, army: Army) -> tuple[bool, str, int]:
        """Perform a morale check for an army.

        Args:
            army: The army to check morale for

        Returns:
            Tuple of (success, consequence_type, roll_value)
                - success: Whether the morale check passed
                - consequence_type: Type of consequence if failed
                - roll_value: The 2d6 roll result
        """
        ...

    def apply_consequence(self, army: Army, consequence: str) -> dict:
        """Apply the consequence of a failed morale check to an army.

        Args:
            army: The army to apply consequence to
            consequence: The consequence type (e.g., "mutiny", "desertion")

        Returns:
            Dictionary with details of what happened
        """
        ...

    def handle_army_rout(self, army: Army) -> dict:
        """Handle an army routing after a battle or morale failure.

        Args:
            army: The routing army

        Returns:
            Dictionary with details of the routing including:
                - army_id: ID of the army
                - supplies_lost: Amount of supplies lost
                - retreat_hexes: Number of hexes retreated
                - status: "routed"
        """
        ...

    def update_army_morale(self, army: Army, change: int) -> None:
        """Update an army's morale by the specified amount.

        Args:
            army: The army to update
            change: Amount to change morale (positive or negative)
        """
        ...
