"""Morale system data structures for Cataphract.

This module provides dataclasses and helper structures to organize
morale-related calculations and consequences.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from cataphract.models import Army


class MoraleConsequenceType(Enum):
    """Enumeration of possible morale consequences."""

    MUTINY = "mutiny"
    MASS_DESERTION = "mass_desertion"
    DEFECT = "defect"
    MAJOR_DESERTION = "major_desertion"
    SPLIT = "split"
    MINOR_DESERTION = "minor_desertion"
    CAMP_FOLLOWERS = "camp_followers"
    TEMPORARY_DEPARTURE = "temporary_departure"
    NO_CONSEQUENCE = "no_consequence"


@dataclass
class MoraleConsequenceResult:
    """Result of applying a morale consequence to an army."""

    consequence_type: MoraleConsequenceType
    applied: bool
    details: dict
    message: str


@dataclass
class ForageParameters:
    """Parameters for foraging operations."""

    army: Army
    target_hexes: list[int]
    weather: str = "clear"


@dataclass
class ForageResult:
    """Result of a foraging operation."""

    success: bool
    foraged_supplies: int
    foraged_hexes: list[int]
    failed_hexes: list[int]
    events: list[str]
    revolt_occurred: bool = False


@dataclass
class TorchParameters:
    """Parameters for torching operations."""

    army: Army
    target_hexes: list[int]
    weather: str = "clear"


@dataclass
class TorchResult:
    """Result of a torching operation."""

    success: bool
    torched_hexes: list[int]
    failed_hexes: list[int]
    events: list[str]
    revolt_occurred: bool = False


# Type alias for consequence handler functions
ConsequenceHandler = Callable[[Army], MoraleConsequenceResult]
