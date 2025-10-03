"""Movement Service Protocol Interface.

This module defines the protocol (interface) for movement-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.models import Army, Hex


class IMovementService(Protocol):
    """Protocol defining the interface for army movement operations.

    This protocol defines the contract for services that handle army movement,
    including standard marches, forced marches, night marches, and river fording.
    """

    def execute_movement(
        self,
        army: Army,
        destination_hex_id: int,
        is_forced_march: bool = False,
        is_night_march: bool = False,
    ) -> dict:
        """Execute an army's movement to a destination hex.

        Args:
            army: Army that's moving
            destination_hex_id: Destination hex ID
            is_forced_march: Whether this is a forced march
            is_night_march: Whether this is a night march

        Returns:
            Dictionary with movement execution results including:
                - success: Whether movement was successful
                - message: Status message
                - new_position: New hex ID if successful
                - movement_time_days: Time taken
                - consumed_supplies: Supplies consumed
        """
        ...

    def calculate_movement_cost(
        self, from_hex: Hex, to_hex: Hex, army: Army, is_road: bool = True
    ) -> float:
        """Calculate movement cost between hexes for an army.

        Args:
            from_hex: Starting hex
            to_hex: Destination hex
            army: Army that's moving
            is_road: Whether the path is on a road

        Returns:
            Movement cost in miles
        """
        ...
