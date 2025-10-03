"""Visibility Service Protocol Interface.

This module defines the protocol (interface) for visibility-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.models import Army, Commander, Hex


class IVisibilityService(Protocol):
    """Protocol defining the interface for visibility-related operations.

    This protocol defines the contract for services that handle fog of war,
    scouting mechanics, and visibility calculations for commanders and armies.
    """

    def calculate_scouting_radius(
        self,
        commander: Commander,
        hex_terrain: str = "flatland",
        weather: str = "clear",
    ) -> int:
        """Calculate the scouting radius for a commander based on army composition and conditions.

        Args:
            commander: The commander whose army determines visibility
            hex_terrain: Terrain type (affects visibility in some cases)
            weather: Current weather (affects visibility)

        Returns:
            Scouting radius in hexes
        """
        ...

    def get_visible_hexes(
        self, commander: Commander, hex_terrain: str = "flatland", weather: str = "clear"
    ) -> list[Hex]:
        """Get all hexes visible to a commander based on their army's scouting radius.

        Args:
            commander: The commander whose visibility to calculate
            hex_terrain: Current terrain (for possible special rules)
            weather: Current weather affecting visibility

        Returns:
            List of visible hexes
        """
        ...

    def get_visible_armies(
        self, commander: Commander, hex_terrain: str = "flatland", weather: str = "clear"
    ) -> list[Army]:
        """Get all armies visible to a commander based on their scouting radius.

        Args:
            commander: The commander whose visibility to calculate
            hex_terrain: Current terrain (for possible special rules)
            weather: Current weather affecting visibility

        Returns:
            List of visible armies
        """
        ...

    def get_scouting_range_for_army(self, army: Army, weather: str = "clear") -> int:
        """Get the scouting range for an army based on its composition and weather.

        Args:
            army: The army to check
            weather: Current weather affecting visibility

        Returns:
            Scouting range in hexes
        """
        ...
