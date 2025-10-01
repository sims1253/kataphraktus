"""Mercenary models for the Cataphract game system.

This module contains models for:
- MercenaryCompanies (catalog of available mercenary companies)
- MercenaryContracts (active contracts between commanders and mercenary companies)
"""

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .army import Army
    from .commander import Commander
    from .game import Game


class MercenaryCompany(Base, TimestampCreatedMixin):
    """Represents a mercenary company available for hire.

    This is a catalog table that defines mercenary companies in the game.
    Each company has base rates and default composition.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        name: Name of the mercenary company
        description: Description of the company
        base_rates: JSON with base daily rates per unit type
        default_composition: JSON array with default unit composition
        available: Whether company is currently available for hire
    """

    __tablename__ = "mercenary_companies"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)

    # Company attributes
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    base_rates: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    default_composition: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    contracts: Mapped[list["MercenaryContract"]] = relationship(
        "MercenaryContract", back_populates="company"
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_mercenary_companies_game_name"),
        Index("idx_merc_companies_game", "game_id"),
        Index("idx_merc_companies_available", "available"),
    )

    def __repr__(self) -> str:
        return f"<MercenaryCompany(id={self.id}, name='{self.name}', available={self.available})>"


class MercenaryContract(Base, TimestampCreatedMixin):
    """Represents an active contract with a mercenary company.

    Contracts track the hire period, upkeep payments, and status.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        company_id: Foreign key to mercenary company
        commander_id: Foreign key to commander hiring the company
        army_id: Foreign key to army if mercenaries are directly attached
        start_day: Game day when contract started
        end_day: Game day when contract ended (NULL if ongoing)
        status: Contract status (active/paused/unpaid/terminated/completed)
        last_upkeep_day: Last game day when upkeep was paid
        negotiated_rates: JSON with negotiated rates (if different from base)
    """

    __tablename__ = "mercenary_contracts"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mercenary_companies.id"), nullable=False
    )
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)
    army_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("armies.id"), nullable=True)

    # Contract attributes
    start_day: Mapped[int] = mapped_column(Integer, nullable=False)
    end_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_upkeep_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    negotiated_rates: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    company: Mapped["MercenaryCompany"] = relationship(
        "MercenaryCompany", back_populates="contracts"
    )
    commander: Mapped["Commander"] = relationship("Commander")
    army: Mapped[Optional["Army"]] = relationship("Army")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'unpaid', 'terminated', 'completed')",
            name="ck_mercenary_contracts_status",
        ),
        Index("idx_merc_contracts_game", "game_id"),
        Index("idx_merc_contracts_commander", "commander_id"),
        Index("idx_merc_contracts_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<MercenaryContract(id={self.id}, company={self.company_id}, status='{self.status}')>"
        )
