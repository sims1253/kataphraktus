"""Next-generation domain model for Cataphract.

This package hosts the new domain-centric architecture that consolidates
all game rules in a single place.  It exposes:

* Dataclasses describing every game entity (see :mod:`models`).
* Enumerations and strongly-typed identifiers used across the rules layer.
* Rule configuration objects (see :mod:`rules_config`).
* Pure rule functions (currently starting with the supply subsystem).

The intent is to replace the current service/domain duplication with a
single cohesive module that can operate purely in-memory and be persisted
through a thin repository adapter.
"""

from . import (
    battle,
    enums,
    harrying,
    mercenaries,
    messaging,
    models,
    morale,
    movement,
    naval,
    operations,
    orders,
    recruitment,
    rules_config,
    siege,
    supply,
    tick,
)

__all__ = [
    "battle",
    "enums",
    "harrying",
    "mercenaries",
    "messaging",
    "models",
    "morale",
    "movement",
    "naval",
    "operations",
    "orders",
    "recruitment",
    "rules_config",
    "siege",
    "supply",
    "tick",
]
