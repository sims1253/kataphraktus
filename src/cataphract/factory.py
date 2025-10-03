"""Service Factory for Cataphract.

This module provides factory functions for creating service instances with
proper dependency wiring. Use these functions in production code to ensure
all service dependencies are correctly initialized.

For testing, inject protocol-based fakes instead of using these factories.

Example:
    # Production usage
    from cataphract.factory import create_supply_service
    supply = create_supply_service(session)

    # Testing usage
    from cataphract.services.supply_service import SupplyService
    from cataphract.interfaces import IVisibilityService

    class FakeVisibility:
        def get_visible_armies(self, commander, **kwargs):
            return []

    supply = SupplyService(session, FakeVisibility())
"""

from sqlalchemy.orm import Session

from cataphract.services.battle_service import BattleService
from cataphract.services.harrying_service import HarryingService
from cataphract.services.morale_service import MoraleService
from cataphract.services.movement_service import MovementService
from cataphract.services.siege_service import SiegeService
from cataphract.services.supply_service import SupplyService
from cataphract.services.visibility_service import VisibilityService


def create_visibility_service(session: Session) -> VisibilityService:
    """Create a VisibilityService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized VisibilityService
    """
    return VisibilityService(session)


def create_supply_service(session: Session) -> SupplyService:
    """Create a SupplyService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized SupplyService with VisibilityService dependency
    """
    visibility = create_visibility_service(session)
    return SupplyService(session, visibility)


def create_harrying_service(session: Session) -> HarryingService:
    """Create a HarryingService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized HarryingService with VisibilityService dependency
    """
    visibility = create_visibility_service(session)
    return HarryingService(session, visibility)


def create_battle_service(session: Session) -> BattleService:
    """Create a BattleService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized BattleService
    """
    return BattleService(session)


def create_morale_service(session: Session) -> MoraleService:
    """Create a MoraleService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized MoraleService
    """
    return MoraleService(session)


def create_siege_service(session: Session) -> SiegeService:
    """Create a SiegeService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized SiegeService with BattleService and MoraleService dependencies
    """
    battle = create_battle_service(session)
    morale = create_morale_service(session)
    return SiegeService(session, battle, morale)


def create_movement_service(session: Session) -> MovementService:
    """Create a MovementService with all dependencies.

    Args:
        session: Database session

    Returns:
        Fully initialized MovementService
    """
    return MovementService(session)


def create_all_services(session: Session) -> dict:
    """Create all services with proper dependency wiring.

    Args:
        session: Database session

    Returns:
        Dictionary containing all initialized services:
        - visibility: VisibilityService
        - supply: SupplyService
        - harrying: HarryingService
        - battle: BattleService
        - morale: MoraleService
        - siege: SiegeService
        - movement: MovementService
    """
    return {
        "visibility": create_visibility_service(session),
        "supply": create_supply_service(session),
        "harrying": create_harrying_service(session),
        "battle": create_battle_service(session),
        "morale": create_morale_service(session),
        "siege": create_siege_service(session),
        "movement": create_movement_service(session),
    }
