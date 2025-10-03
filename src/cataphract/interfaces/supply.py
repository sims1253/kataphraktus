"""Supply Service Protocol Interface.

This module defines the protocol (interface) for supply-related services
in the Cataphract game system.
"""

from typing import Protocol

from cataphract.domain.morale_data import (
    ForageParameters,
    ForageResult,
    TorchParameters,
    TorchResult,
)
from cataphract.models import Army


class ISupplyService(Protocol):
    """Protocol defining the interface for supply logistics operations.

    This protocol defines the contract for services that handle supply consumption,
    foraging, torching, and supply transfers in the Cataphract game system.
    """

    def consume_supplies(self, army: Army) -> dict:
        """Consume daily supplies for an army.

        Args:
            army: The army to consume supplies for

        Returns:
            Dictionary with consumption results including:
                - consumed: Amount consumed
                - resulting_supplies: Remaining supplies
                - starvation_days: Days without supplies
                - army_status: "normal", "starving", or "dissolved"
        """
        ...

    def forage(self, params: ForageParameters) -> ForageResult:
        """Allow an army to forage supplies from nearby hexes.

        Args:
            params: ForageParameters containing all necessary information

        Returns:
            ForageResult with foraging outcomes
        """
        ...

    def torch(self, params: TorchParameters) -> TorchResult:
        """Allow an army to torch hexes, preventing foraging until spring.

        Args:
            params: TorchParameters containing all necessary information

        Returns:
            TorchResult with torching outcomes
        """
        ...
