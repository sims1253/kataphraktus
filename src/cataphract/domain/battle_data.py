"""Battle data structures for Cataphract.

This module provides dataclasses and helper structures to organize
battle-related parameters and reduce function complexity.
"""

from dataclasses import dataclass

from cataphract.models import Army


@dataclass
class BattleParameters:
    """Encapsulates all parameters for battle resolution."""

    attacker_armies: list[Army]
    defender_armies: list[Army]
    hex_id: int
    hex_terrain: str = "flatland"
    weather: str = "clear"
    is_assault: bool = False
    fortress_defense_bonus: int = 0


@dataclass
class BattleContext:
    """Context object for battle calculations and state management."""

    parameters: BattleParameters
    attacker_rolls: dict[int, int]  # army_id -> roll result
    defender_rolls: dict[int, int]  # army_id -> roll result
    highest_attacker_roll: int
    highest_defender_roll: int
    winning_side: str  # "attacker" or "defender"

    @property
    def attacker_armies(self) -> list[Army]:
        """Get attacker armies from parameters."""
        return self.parameters.attacker_armies

    @property
    def defender_armies(self) -> list[Army]:
        """Get defender armies from parameters."""
        return self.parameters.defender_armies

    @property
    def all_armies(self) -> list[Army]:
        """Get all armies in the battle."""
        return self.attacker_armies + self.defender_armies


@dataclass
class ArmyBattleState:
    """Tracks the battle state for a single army."""

    army: Army
    base_roll: int
    modifiers: int
    final_roll: int
    casualties_percentage: float
    morale_change: int
    is_captured: bool = False


@dataclass
class BattleModifierParameters:
    """Parameters for calculating battle modifiers."""

    army: Army
    is_attacker: bool
    is_defender: bool
    hex_terrain: str = "flatland"
    weather: str = "clear"
    is_assault: bool = False


@dataclass
class BattleOutcome:
    """Container for battle outcome results."""

    casualties: dict
    morale_changes: dict
    routed_armies: list
    commanders_captured: list


@dataclass
class BattleRollResults:
    """Container for battle roll results."""

    attacker_rolls: dict[int, int]
    defender_rolls: dict[int, int]
