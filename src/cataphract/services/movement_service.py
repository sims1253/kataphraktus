"""Movement Service for Cataphract.

This module provides functions for managing army movement including standard,
forced, night marches, and river fording according to the Cataphract rules.
"""

from sqlalchemy.orm import Session

from cataphract.models import Army, Hex, RiverCrossing
from cataphract.utils.hex_math import HexCoord, hex_distance
from cataphract.utils.rng import generate_seed, roll_dice

# Movement constants
NIGHT_MARCH_SPEED = 6.0  # miles per hour for night marches
FORCED_MARCH_DAYS_PER_WEEK = 7  # maximum days in forced march week
STANDARD_MARCH_DAYS_PER_WEEK = 5  # standard days per week
RIVER_FORDING_DIVISOR = 2  # infantry river crossing time divisor
SCOUTING_RADIUS_CAVALRY = 2  # additional hex range for cavalry scouting
OFFROAD_REGULAR_SPEED = 6.0  # miles per day for regular off-road movement
OFFROAD_FORCED_SPEED = 9.0  # miles per day for forced off-road movement
MAX_COLUMN_LENGTH_NORMAL = 6.0  # maximum column length before speed reduction
NIGHT_MARCH_WRONG_PATH_CHANCE = 2  # roll threshold for taking wrong path (2-in-6)


class MovementService:
    """Service for handling movement mechanics in Cataphract."""

    def __init__(self, session: Session):
        self.session = session

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
        # Calculate distance between hexes
        from_coord = HexCoord(q=from_hex.q, r=from_hex.r)
        to_coord = HexCoord(q=to_hex.q, r=to_hex.r)
        distance = hex_distance(from_coord, to_coord)

        # Each hex is 6 miles across, so base cost is distance * 6
        base_cost = distance * 6.0

        # On roads, movement is at full speed (base cost)
        # Off-road, movement is at half speed
        if not is_road:
            # Check if army has wagons (they can't travel off-road)
            total_wagons = 0
            for detachment in army.detachments:
                total_wagons += detachment.wagon_count

            if total_wagons > 0:
                # Wagons cannot travel off-road
                return float("inf")  # Movement impossible

            # For armies without wagons, off-road is half speed
            return base_cost * 2.0

        return base_cost

    def calculate_army_column_length(self, army: Army) -> float:
        """Calculate the length of an army column in miles.

        Args:
            army: Army to calculate column length for

        Returns:
            Column length in miles
        """
        total_soldiers = 0
        total_cavalry = 0
        total_wagons = 0

        for detachment in army.detachments:
            if detachment.unit_type.category == "cavalry":
                total_cavalry += detachment.soldier_count
            else:
                total_soldiers += detachment.soldier_count
            total_wagons += detachment.wagon_count

        # Calculate column length: 1 mile per 5,000 infantry+NC, 2,000 cavalry, 50 wagons
        noncombatants = army.noncombatant_count
        infantry_miles = (total_soldiers + noncombatants) / 5000.0
        cavalry_miles = total_cavalry / 2000.0
        wagon_miles = total_wagons / 50.0

        # Army column length is determined by the longest component
        # Rules: "marching armies stretch 1 mile of road per 5,000 infantry and noncombatants,
        # 2,000 cavalry, or 50 wagons" - use the maximum of these
        return max(infantry_miles, cavalry_miles, wagon_miles)

    def can_move_offroad(self, army: Army) -> bool:
        """Check if an army can move off-road based on unit types and wagons.

        Args:
            army: Army to check

        Returns:
            True if army can move off-road, False otherwise
        """
        # Check each detachment for off-road capability
        for detachment in army.detachments:
            # If any detachment has wagons, they can't go off-road
            if detachment.wagon_count > 0:
                return False

            # Check if unit type can travel off-road
            if not detachment.unit_type.can_travel_offroad and (
                not detachment.unit_type.special_abilities
                or not detachment.unit_type.special_abilities.get("offroad_full_speed")
            ):
                return False

        return True

    def calculate_fording_time(self, army: Army) -> float:
        """Calculate time required for an army to ford a river.

        Args:
            army: Army fording the river

        Returns:
            Time in days to ford
        """
        # Only infantry and noncombatants delay fording
        # Cavalry cross at regular speed
        # Wagons cannot ford (should be prevented by movement validation)
        total_soldiers = 0
        for detachment in army.detachments:
            if detachment.unit_type.category != "cavalry":
                total_soldiers += detachment.soldier_count

        noncombatants = army.noncombatant_count
        total_infantry_nc = total_soldiers + noncombatants

        # Each mile of infantry column requires 0.5 days to ford
        infantry_column_miles = total_infantry_nc / 5000.0
        fording_time = infantry_column_miles * 0.5  # half day per mile

        return max(0.5, fording_time)  # Minimum time is 0.5 days

    def can_ford_with_wagons(self, army: Army) -> bool:
        """Check if an army can ford a river with wagons.

        Args:
            army: Army to check

        Returns:
            True if army can ford with wagons, False otherwise
        """
        # Wagons cannot ford rivers
        total_wagons = 0
        for detachment in army.detachments:
            total_wagons += detachment.wagon_count

        return total_wagons == 0

    def calculate_movement_speed(
        self,
        army: Army,
        is_road: bool = True,
        is_forced_march: bool = False,
        is_night_march: bool = False,
    ) -> float:
        """Calculate an army's movement speed based on conditions.

        Args:
            army: Army to calculate speed for
            is_road: Whether on a road
            is_forced_march: Whether forced march
            is_night_march: Whether night march

        Returns:
            Movement speed in miles per day
        """
        if is_night_march:
            # Night march: 6 miles/night (12 if forced)
            return 12.0 if is_forced_march else 6.0

        # Base movement speed
        if is_road:
            # On road: 18 miles/day if forced, 12 miles/day regular
            speed = 18.0 if is_forced_march else 12.0
        elif is_forced_march:
            # Forced march off-road: 9 miles/day
            speed = OFFROAD_FORCED_SPEED
        else:
            # Regular off-road: 6 miles/day
            speed = OFFROAD_REGULAR_SPEED

        # Check if army is too long (moves at reduced speed)
        column_length = self.calculate_army_column_length(army)
        if column_length > MAX_COLUMN_LENGTH_NORMAL:
            # Long armies move at 6 miles/day (30 miles/week) or 12 if forced (72 miles/week)
            if is_forced_march:
                return 12.0
            return 6.0

        # Cavalry-only forced march double speed
        if is_forced_march and self._is_cavalry_only(army):
            return speed * 2.0

        return speed

    def _is_cavalry_only(self, army: Army) -> bool:
        """Check if army consists only of cavalry detachments.

        Args:
            army: Army to check

        Returns:
            True if army is cavalry only, False otherwise
        """
        if not army.detachments:
            return False
        return all(detachment.unit_type.category == "cavalry" for detachment in army.detachments)

    def calculate_forced_march_morale_loss(self, army: Army, days_this_week: int) -> dict:
        """Calculate morale loss from forced marching.

        Args:
            army: Army that's forced marching
            days_this_week: Number of days marched this week

        Returns:
            Dictionary with morale loss details
        """
        result = {"morale_loss": 0, "should_check_morale": False, "days_threshold_crossed": 0}

        # Each cumulative week of forced march causes -1 morale loss
        # This happens when crossing the integer threshold (e.g. going from 6.9 to 7.0 days)
        prev_weeks = int(army.forced_march_weeks)
        new_weeks = army.forced_march_weeks + (days_this_week / 7.0)
        new_weeks_int = int(new_weeks)

        if new_weeks_int > prev_weeks:
            # Crossed an integer week threshold
            morale_loss = new_weeks_int - prev_weeks
            result["morale_loss"] = morale_loss
            result["should_check_morale"] = True
            result["days_threshold_crossed"] = new_weeks_int * 7

            # Apply Stubborn trait if present (no morale loss on defeat, but this is different)
            has_stubborn = False
            if army.commander:
                for trait in army.commander.traits:
                    if trait.trait.name.lower() == "stubborn":
                        has_stubborn = True
                        break

            if not has_stubborn:
                army.morale_current = max(0, army.morale_current - morale_loss)

        # Update cumulative forced march weeks
        army.forced_march_weeks = new_weeks

        return result

    def plan_movement_route(self, army: Army, start_hex_id: int, destination_hex_id: int) -> dict:
        """Plan an army's movement route between hexes.

        Args:
            army: Army that's moving
            start_hex_id: Starting hex ID
            destination_hex_id: Destination hex ID

        Returns:
            Dictionary with route planning details
        """
        result = {
            "success": False,
            "route": [],
            "total_distance": 0,
            "estimated_time_days": 0,
            "obstacles": [],
            "warnings": [],
        }

        start_hex = self.session.get(Hex, start_hex_id)
        dest_hex = self.session.get(Hex, destination_hex_id)

        if not start_hex or not dest_hex:
            result["error"] = "Start or destination hex not found"
            return result

        # Check if army can travel off-road if the route is off-road
        if not start_hex.has_road and not dest_hex.has_road and not self.can_move_offroad(army):
            result["error"] = "Army cannot travel off-road"
            return result

        # Calculate distance
        from_coord = HexCoord(q=start_hex.q, r=start_hex.r)
        to_coord = HexCoord(q=dest_hex.q, r=dest_hex.r)
        distance = hex_distance(from_coord, to_coord)

        result["total_distance"] = distance * 6  # 6 miles per hex

        # Simple straight path (in a real implementation, use pathfinding)
        # For now, just return direct path
        _current_q, _current_r = start_hex.q, start_hex.r
        _dest_q, _dest_r = dest_hex.q, dest_hex.r

        # Calculate path (simplified - real implementation would use A* or similar)

        # For direct path, we'll just note the start and end for now
        # A full implementation would find the path via pathfinding algorithms
        result["route"] = [
            {
                "from_hex_id": start_hex_id,
                "to_hex_id": destination_hex_id,
                "distance": distance * 6,
                "is_road": start_hex.has_road and dest_hex.has_road,
                "terrain": dest_hex.terrain_type,
            }
        ]

        # Calculate estimated time based on army's speed
        # This is simplified; in reality, would compute segment by segment
        avg_speed = self.calculate_movement_speed(army, is_road=start_hex.has_road)
        estimated_time = result["total_distance"] / avg_speed
        result["estimated_time_days"] = estimated_time
        result["success"] = True

        return result

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
            Dictionary with movement execution results
        """
        result = {
            "success": False,
            "message": "",
            "new_position": None,
            "movement_time_days": 0,
            "consumed_supplies": 0,
        }

        # Validate movement constraints
        validation_result = self._validate_movement_constraints(
            army, destination_hex_id, is_forced_march, is_night_march
        )
        if not validation_result["can_move"]:
            result["message"] = "; ".join(validation_result["errors"])
            return result

        # Calculate movement details
        movement_details = self._calculate_movement_details(
            army, destination_hex_id, is_forced_march, is_night_march
        )
        if not movement_details["success"]:
            result["message"] = movement_details["error"]
            return result

        # Execute the movement
        execution_result = self._perform_movement_execution(
            army, destination_hex_id, movement_details, is_forced_march, is_night_march
        )

        # Combine results
        result.update(execution_result)
        result["success"] = True

        return result

    def _validate_movement_constraints(
        self, army: Army, destination_hex_id: int, is_forced_march: bool, is_night_march: bool
    ) -> dict:
        """Validate all movement constraints before execution."""
        validation_result = {"can_move": True, "errors": []}

        # Validate destination hex exists
        destination_hex = self.session.get(Hex, destination_hex_id)
        if not destination_hex:
            validation_result["can_move"] = False
            validation_result["errors"].append("Destination hex not found")
            return validation_result

        # Check weekly march limits
        if is_forced_march:
            if army.days_marched_this_week >= FORCED_MARCH_DAYS_PER_WEEK:
                validation_result["can_move"] = False
                validation_result["errors"].append(
                    f"Army cannot forced march more than {FORCED_MARCH_DAYS_PER_WEEK} days per week"
                )
        elif army.days_marched_this_week >= STANDARD_MARCH_DAYS_PER_WEEK:
            validation_result["can_move"] = False
            validation_result["errors"].append(
                f"Army cannot march more than {STANDARD_MARCH_DAYS_PER_WEEK} days per week"
            )

        # Check off-road capability
        if not destination_hex.has_road and not self.can_move_offroad(army):
            validation_result["can_move"] = False
            validation_result["errors"].append(
                "Army with wagons or non-offroad units cannot move off-road"
            )

        # Check night march road requirement
        if is_night_march and not destination_hex.has_road:
            validation_result["can_move"] = False
            validation_result["errors"].append("Night marches cannot go off-road")

        return validation_result

    def _calculate_movement_details(
        self, army: Army, destination_hex_id: int, is_forced_march: bool, is_night_march: bool
    ) -> dict:
        """Calculate movement time, distance, and river crossing details."""
        result = {"success": True, "error": None, "movement_time": 0, "total_distance": 0}

        # Get start and destination hexes
        start_hex = self.session.get(Hex, army.current_hex_id)
        destination_hex = self.session.get(Hex, destination_hex_id)

        if not start_hex:
            result["success"] = False
            result["error"] = "Army's current hex not found"
            return result

        # Calculate distance
        from_coord = HexCoord(q=start_hex.q, r=start_hex.r)
        to_coord = HexCoord(q=destination_hex.q, r=destination_hex.r)
        distance_hexes = hex_distance(from_coord, to_coord)
        total_distance = distance_hexes * 6  # 6 miles per hex
        result["total_distance"] = total_distance

        # Check for river crossings
        river_crossings = self._check_river_crossings(army, start_hex, destination_hex)

        # Handle river fording if necessary
        total_fording_time = 0
        for crossing in river_crossings:
            if crossing.crossing_type == "ford":
                if not self.can_ford_with_wagons(army):
                    result["success"] = False
                    result["error"] = "Army with wagons cannot ford rivers"
                    return result
                fording_time = self.calculate_fording_time(army)
                total_fording_time += fording_time

        # Calculate movement speed
        speed = self.calculate_movement_speed(
            army, start_hex.has_road, is_forced_march, is_night_march
        )
        movement_time = total_distance / speed + total_fording_time
        result["movement_time"] = movement_time

        return result

    def _perform_movement_execution(
        self,
        army: Army,
        destination_hex_id: int,
        movement_details: dict,
        is_forced_march: bool,
        is_night_march: bool,
    ) -> dict:
        """Execute the actual movement and update army state."""
        result = {
            "new_position": destination_hex_id,
            "movement_time_days": movement_details["movement_time"],
            "message": f"Movement to hex {destination_hex_id} initiated",
        }

        # Update army status
        army.status = "forced_march" if is_forced_march else "marching"
        if is_night_march:
            army.status = "night_march"

        # Update army position
        army.current_hex_id = destination_hex_id
        army.destination_hex_id = None

        # Update weekly march counter
        army.days_marched_this_week += 1

        # Handle forced march morale effects
        if is_forced_march:
            morale_result = self.calculate_forced_march_morale_loss(
                army, army.days_marched_this_week
            )
            if morale_result["morale_loss"] > 0:
                result["message"] += (
                    f" Forced march caused {morale_result['morale_loss']} morale loss."
                )

        # Handle night march effects
        if is_night_march:
            result["message"] += " Night march conducted (morale check required at destination)."
            self._check_night_march_path_finding(army, destination_hex_id, result)

        return result

    def _check_night_march_path_finding(
        self, army: Army, destination_hex_id: int, result: dict
    ) -> None:
        """Check for wrong path at road forks during night marches."""
        seed = generate_seed(
            army.id,
            army.game.current_day,
            army.game.current_day_part,
            f"wrong_path_{destination_hex_id}",
        )
        roll_result = roll_dice(seed, "1d6")
        if roll_result["total"] <= NIGHT_MARCH_WRONG_PATH_CHANCE:
            result["message"] += " During night march, army took wrong path at fork."

    def _check_river_crossings(
        self, _army: Army, _start_hex: Hex, _end_hex: Hex
    ) -> list[RiverCrossing]:
        """Check for any river crossings between two hexes.

        Args:
            _army: Army that's moving (unused for now)
            _start_hex: Starting hex (unused for now)
            _end_hex: Ending hex (unused for now)

        Returns:
            List of river crossings that must be traversed
        """
        # For now, return an empty list
        # In a real implementation, this would query the river_crossings table
        # to find if there are any rivers to cross between start_hex and end_hex
        return []

    def check_movement_constraints(
        self,
        army: Army,
        destination_hex_id: int,
        is_forced_march: bool = False,
        is_night_march: bool = False,
    ) -> dict:
        """Check all constraints before allowing army movement.

        Args:
            army: Army that wants to move
            destination_hex_id: Destination hex
            is_forced_march: Whether forced march
            is_night_march: Whether night march

        Returns:
            Dictionary with validation results
        """
        result = {"can_move": True, "errors": [], "warnings": []}

        # Check if destination hex exists
        destination_hex = self.session.get(Hex, destination_hex_id)
        if not destination_hex:
            result["can_move"] = False
            result["errors"].append("Destination hex does not exist")
            return result

        # Check if army has wagons and is trying to go off-road
        if not destination_hex.has_road and not self.can_move_offroad(army):
            result["can_move"] = False
            result["errors"].append("Army with wagons or non-offroad units cannot move off-road")

        # Check if night march is on road (rule: cannot go off-road at night)
        if is_night_march and not destination_hex.has_road:
            result["can_move"] = False
            result["errors"].append("Night marches cannot go off-road")

        # Check if forced march day limit exceeded
        if is_forced_march and army.days_marched_this_week >= FORCED_MARCH_DAYS_PER_WEEK:
            result["warnings"].append(
                f"Army at forced march day limit ({FORCED_MARCH_DAYS_PER_WEEK}/week)"
            )
        elif not is_forced_march and army.days_marched_this_week >= STANDARD_MARCH_DAYS_PER_WEEK:
            result["warnings"].append(
                f"Army at regular march day limit ({STANDARD_MARCH_DAYS_PER_WEEK}/week)"
            )

        # Check for river crossings that require wagons to ford (impossible)
        # This would be implemented in a real system

        return result
