"""Visibility and Scouting Service for Cataphract.

This module provides functions for managing fog of war and calculating what
a commander can see based on their army's composition and game conditions.
"""

from sqlalchemy.orm import Session

from cataphract.domain.supply import detachment_has_ability
from cataphract.models import Army, Commander, CommanderVisibility, Hex
from cataphract.utils.hex_math import HexCoord, hexes_in_range

# Visibility constants
CAVALRY_SCOUTING_RADIUS = 2  # base scouting radius for cavalry
OUTRIDER_MINIMUM_RADIUS = 2  # minimum radius required for Outrider trait to work


class VisibilityService:
    """Service for handling visibility mechanics in Cataphract."""

    def __init__(self, session: Session):
        self.session = session

    def calculate_scouting_radius(
        self,
        commander: Commander,
        weather: str = "clear",
    ) -> int:
        """Calculate the scouting radius for a commander based on army composition and conditions.

        Args:
            commander: The commander whose army determines visibility
            weather: Current weather (affects visibility)

        Returns:
            Scouting radius in hexes
        """
        # Get the commander's first army and delegate to get_scouting_range_for_army
        if not commander.armies:
            return 1  # Base radius if no army

        army = commander.armies[0]  # Use first army
        return self.get_scouting_range_for_army(army, weather)

    def get_visible_hexes(self, commander: Commander, weather: str = "clear") -> list[Hex]:
        """Get all hexes visible to a commander based on their army's scouting radius.

        Args:
            commander: The commander whose visibility to calculate
            weather: Current weather affecting visibility

        Returns:
            List of visible hexes
        """
        # Get the commander's current location
        if not commander.current_hex_id:
            return []

        current_hex = self.session.get(Hex, commander.current_hex_id)
        if not current_hex:
            return []

        # Calculate scouting radius
        radius = self.calculate_scouting_radius(commander, weather)

        # If radius is 0, only return the current hex
        if radius <= 0:
            return [current_hex]

        # Create HexCoord objects for distance calculation
        center_coord = HexCoord(q=current_hex.q, r=current_hex.r)

        # Find hexes in range using the hex_math utility
        hexes_in_radius = hexes_in_range(center_coord, radius)

        # Find corresponding hex objects in the database
        visible_hexes = []
        for hex_coord in hexes_in_radius:
            target_hex = (
                self.session.query(Hex)
                .filter(
                    Hex.game_id == current_hex.game_id, Hex.q == hex_coord.q, Hex.r == hex_coord.r
                )
                .first()
            )

            if target_hex:
                visible_hexes.append(target_hex)

        return visible_hexes

    def get_visible_armies(self, commander: Commander, weather: str = "clear") -> list[Army]:
        """Get all armies visible to a commander based on their scouting radius.

        Args:
            commander: The commander whose visibility to calculate
            weather: Current weather affecting visibility

        Returns:
            List of visible armies
        """
        visible_hexes = self.get_visible_hexes(commander, weather)
        visible_hex_ids = [h.id for h in visible_hexes]

        # Find all armies in visible hexes
        return self.session.query(Army).filter(Army.current_hex_id.in_(visible_hex_ids)).all()

    def update_commander_visibility(self, commander_id: int, game_day: int, game_part: str):
        """Update the cached visibility for a commander at the current game state.

        Args:
            commander_id: ID of the commander
            game_day: Current game day
            game_part: Current day part (morning, midday, evening, night)
        """
        commander = self.session.get(Commander, commander_id)
        if not commander:
            return

        # Calculate current visibility
        visible_hexes = self.get_visible_hexes(commander)
        visible_armies = self.get_visible_armies(commander)
        # For now, we'll just store the hex IDs in the simplified format
        visible_hex_ids = [h.id for h in visible_hexes]
        visible_army_ids = [a.id for a in visible_armies]

        # Check if a record already exists for this commander/day/part
        existing_record = (
            self.session.query(CommanderVisibility)
            .filter(
                CommanderVisibility.commander_id == commander_id,
                CommanderVisibility.game_day == game_day,
                CommanderVisibility.game_part == game_part,
            )
            .first()
        )

        if existing_record:
            # Update existing record
            existing_record.visible_hex_ids = visible_hex_ids
            existing_record.known_armies = {"army_ids": visible_army_ids}
        else:
            # Create new record
            visibility_record = CommanderVisibility(
                commander_id=commander_id,
                game_day=game_day,
                game_part=game_part,
                visible_hex_ids=visible_hex_ids,
                known_armies={"army_ids": visible_army_ids},
            )
            self.session.add(visibility_record)

        self.session.commit()

    def is_hex_visible_to_commander(
        self,
        hex_id: int,
        commander: Commander,
        weather: str = "clear",
    ) -> bool:
        """Check if a specific hex is visible to a commander.

        Args:
            hex_id: ID of the hex to check
            commander: The commander to check visibility for
            weather: Current weather affecting visibility

        Returns:
            True if hex is visible, False otherwise
        """
        visible_hexes = self.get_visible_hexes(commander, weather)
        visible_hex_ids = [h.id for h in visible_hexes]
        return hex_id in visible_hex_ids

    def get_scouting_range_for_army(self, army: Army, weather: str = "clear") -> int:
        """Get the scouting range for an army based on its composition and weather.

        Args:
            army: The army to check
            weather: Current weather affecting visibility

        Returns:
            Scouting range in hexes
        """
        # Base radius is 1 (current hex + 1 adjacent ring)
        radius = 1

        # If army has cavalry, radius increases to 2
        for detachment in army.detachments:
            if detachment.unit_type.category == "cavalry" or detachment_has_ability(
                detachment, "acts_as_cavalry_for_scouting"
            ):
                # Cavalry and designated skirmishers extend the radius
                radius = CAVALRY_SCOUTING_RADIUS
                break

        # Check for Outrider trait (with cavalry, 3-hex scouting)
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "outrider" and radius >= OUTRIDER_MINIMUM_RADIUS:
                    radius = 3
                    break

        # Check for Ranger trait: Ignore weather penalties to scouting radius
        has_ranger = False
        if army.commander:
            for trait in army.commander.traits:
                if trait.trait.name.lower() == "ranger":
                    has_ranger = True
                    break

        # Bad weather reduces radius (unless Ranger)
        if not has_ranger:
            if weather in ["bad", "storm"]:
                radius -= 1
            elif weather == "very_bad":
                radius -= 2

        # Minimum radius is 0
        return max(0, radius)
