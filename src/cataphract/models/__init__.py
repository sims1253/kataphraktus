"""SQLAlchemy models for the Cataphract game system.

This module exports all database models and provides access to the
declarative base and seed data functions.
"""

# Base classes
# Army models
from .army import Army, Detachment, MovementLeg, UnitType
from .base import Base, TimestampCreatedMixin, TimestampMixin, utc_now

# Battle models
from .battle import Battle

# Commander models
from .commander import Commander, CommanderTrait, Trait

# Event models
from .event import Event

# Faction models
from .faction import Faction, FactionRelation

# Core game models
from .game import Game

# Map-related models
from .map import CrossingQueue, Hex, MapFeature, RiverCrossing, RoadEdge

# Mercenary models
from .mercenary import MercenaryCompany, MercenaryContract

# Message models
from .message import Message, MessageLeg

# Naval models
from .naval import Ship, ShipType

# Operation models
from .operation import Operation

# Order models
from .order import Order, OrdersLogEntry

# Player models
from .player import Player

# Seed data functions
from .seed_data import seed_all_catalog_data, seed_traits, seed_unit_types

# Siege models
from .siege import Siege

# Stronghold models
from .stronghold import Stronghold

# Visibility models
from .visibility import CommanderVisibility

# Weather models
from .weather import Weather

__all__ = [
    "Army",
    "Base",
    "Battle",
    "Commander",
    "CommanderTrait",
    "CommanderVisibility",
    "CrossingQueue",
    "Detachment",
    "Event",
    "Faction",
    "FactionRelation",
    "Game",
    "Hex",
    "MapFeature",
    "MercenaryCompany",
    "MercenaryContract",
    "Message",
    "MessageLeg",
    "MovementLeg",
    "Operation",
    "Order",
    "OrdersLogEntry",
    "Player",
    "RiverCrossing",
    "RoadEdge",
    "Ship",
    "ShipType",
    "Siege",
    "Stronghold",
    "TimestampCreatedMixin",
    "TimestampMixin",
    "Trait",
    "UnitType",
    "Weather",
    "seed_all_catalog_data",
    "seed_traits",
    "seed_unit_types",
    "utc_now",
]
