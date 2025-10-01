"""Operation model for the Cataphract game system.

This module contains the model for operations, which are covert
actions commissioned by commanders.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .commander import Commander
    from .game import Game


class Operation(Base, TimestampCreatedMixin):
    """Represents a covert operation.

    Operations are special actions commissioned by commanders for loot.
    They target commanders, armies, strongholds, or hexes and have
    success/failure based on 2d6 rolls.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        commander_id: Foreign key to commander commissioning the operation
        operation_type: Type of operation (custom string)
        target_type: Type of target (commander/army/stronghold/hex)
        target_id: ID of the target entity
        description: Description of the operation
        loot_cost: Loot cost to commission (default 100)
        complexity: Complexity level (simple/moderate/complex)
        success_target: Target number for 2d6 roll
        roll_result: Actual 2d6 roll result
        success: Whether operation succeeded
        result_details: JSON with detailed outcome
        commissioned_on_day: Game day when commissioned
        executed_on_day: Game day when executed
    """

    __tablename__ = "operations"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)

    # Operation attributes
    operation_type: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    loot_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    complexity: Mapped[str] = mapped_column(String, nullable=False)
    success_target: Mapped[int] = mapped_column(Integer, nullable=False)
    roll_result: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    commissioned_on_day: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_on_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    commander: Mapped["Commander"] = relationship("Commander")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "complexity IN ('simple', 'moderate', 'complex')",
            name="ck_operations_complexity",
        ),
        Index("idx_operations_commander", "commander_id"),
        Index("idx_operations_status", "executed_on_day"),
    )

    def __repr__(self) -> str:
        return f"<Operation(id={self.id}, type='{self.operation_type}', commissioned_day={self.commissioned_on_day})>"
