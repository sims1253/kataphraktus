"""Enumerations and type aliases for the new Cataphract domain."""

from __future__ import annotations

from enum import StrEnum


class DayPart(StrEnum):
    """Enumerates the four day parts used by the daily tick."""

    MORNING = "morning"
    MIDDAY = "midday"
    EVENING = "evening"
    NIGHT = "night"


class Season(StrEnum):
    """Season of the in-world calendar."""

    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class ArmyStatus(StrEnum):
    """Simplified army states derived from the ruleset."""

    IDLE = "idle"
    MARCHING = "marching"
    FORCED_MARCH = "forced_march"
    NIGHT_MARCH = "night_march"
    RESTING = "resting"
    FORAGING = "foraging"
    TORCHING = "torching"
    BESIEGING = "besieging"
    IN_BATTLE = "in_battle"
    HARRYING = "harrying"
    ROUTED = "routed"
    GARRISONED = "garrisoned"


class HexTerrain(StrEnum):
    """Terrain types present in the ruleset."""

    FLATLAND = "flatland"
    HILLS = "hills"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    WATER = "water"
    COAST = "coast"


class StrongholdType(StrEnum):
    """Stronghold classifications."""

    TOWN = "town"
    CITY = "city"
    FORTRESS = "fortress"


class RelationType(StrEnum):
    """Faction relationship states."""

    ALLIED = "allied"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"


class MessengerTerritory(StrEnum):
    """Territory classification for messenger speed/odds."""

    FRIENDLY = "friendly"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"


class MovementType(StrEnum):
    """Movement modes an order may request."""

    STANDARD = "standard"
    FORCED = "forced"
    NIGHT = "night"


class OrderStatus(StrEnum):
    """Order lifecycle states."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SiegeStatus(StrEnum):
    """Possible siege outcomes."""

    ONGOING = "ongoing"
    GATES_OPENED = "gates_opened"
    SUCCESSFUL_ASSAULT = "successful_assault"
    LIFTED = "lifted"


class NavalStatus(StrEnum):
    """Fleet status values."""

    AVAILABLE = "available"
    TRANSPORTING = "transporting"
    FLED = "fled"


class OperationType(StrEnum):
    """Operation categories used in the espionage rules."""

    INTELLIGENCE = "intelligence"
    ASSASSINATION = "assassination"
    SABOTAGE = "sabotage"


class OperationOutcome(StrEnum):
    """Possible operation results."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"
