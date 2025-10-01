"""Order models for the Cataphract game system.

This module contains models for:
- Orders (commands issued to armies)
- OrdersLogEntries (referee workflow management)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .army import Army
    from .commander import Commander
    from .event import Event
    from .game import Game
    from .message import Message


class Order(Base, TimestampCreatedMixin):
    """Represents an order issued to an army.

    Orders are commands that armies execute at specific game times.
    They can be movement orders, foraging orders, battle orders, etc.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        commander_id: Foreign key to commander issuing the order
        army_id: Foreign key to army receiving the order
        order_type: Type of order (move/forage/besiege/etc)
        parameters: JSON object with order-specific parameters
        issued_at: Real-world timestamp when order was issued
        execute_at_day: Game day when order should execute
        execute_at_part: Daypart when order should execute
        status: Order status (pending/executing/completed/cancelled/failed)
        result: JSON object with outcome (once executed)
        executed_at_day: Game day when order was executed
        executed_at_part: Daypart when order was executed
    """

    __tablename__ = "orders"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    commander_id: Mapped[int] = mapped_column(Integer, ForeignKey("commanders.id"), nullable=False)
    army_id: Mapped[int] = mapped_column(Integer, ForeignKey("armies.id"), nullable=False)

    # Order attributes
    order_type: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execute_at_day: Mapped[int] = mapped_column(Integer, nullable=False)
    execute_at_part: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    executed_at_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executed_at_part: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="orders")
    commander: Mapped["Commander"] = relationship("Commander")
    army: Mapped["Army"] = relationship("Army", back_populates="orders")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "order_type IN ('move', 'forced_march', 'night_march', 'rest', 'forage', 'torch', "
            "'besiege', 'assault', 'harry', 'transfer_supplies', 'give_loot', "
            "'embark', 'disembark', 'split_army', 'garrison', 'ungarrison')",
            name="ck_orders_type",
        ),
        CheckConstraint(
            "execute_at_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_orders_execute_at_part",
        ),
        CheckConstraint(
            "executed_at_part IS NULL OR executed_at_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_orders_executed_at_part",
        ),
        CheckConstraint(
            "status IN ('pending', 'executing', 'completed', 'cancelled', 'failed')",
            name="ck_orders_status",
        ),
        Index("idx_orders_army", "army_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_execute_time", "execute_at_day", "execute_at_part"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, type='{self.order_type}', army={self.army_id}, status='{self.status}')>"


class OrdersLogEntry(Base, TimestampCreatedMixin):
    """Represents an entry in the referee's orders log.

    The orders log helps the referee manage game workflow by tracking
    what needs to be done each game tick (deliveries, events, etc).

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        game_day: Game day this entry is for
        game_part: Daypart this entry is for
        entry_type: Type of entry (notice/delivery/completion/event/sighting)
        description: Human-readable description for referee
        related_event_id: Foreign key to related event (if applicable)
        related_commander_id: Foreign key to related commander (if applicable)
        related_message_id: Foreign key to related message (if applicable)
        priority: Priority level (low/normal/high/urgent)
        status: Status of this entry (pending/sent/deferred/skipped)
        processed_at: Real-world timestamp when processed
    """

    __tablename__ = "orders_log_entries"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    related_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=True
    )
    related_commander_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=True
    )
    related_message_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("messages.id"), nullable=True
    )

    # Log entry attributes
    game_day: Mapped[int] = mapped_column(Integer, nullable=False)
    game_part: Mapped[str] = mapped_column(String, nullable=False)
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship("Game")
    related_event: Mapped[Optional["Event"]] = relationship("Event")
    related_commander: Mapped[Optional["Commander"]] = relationship("Commander")
    related_message: Mapped[Optional["Message"]] = relationship("Message")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "game_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_orders_log_entries_game_part",
        ),
        CheckConstraint(
            "entry_type IN ('notice', 'delivery', 'completion', 'event', 'sighting')",
            name="ck_orders_log_entries_type",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_orders_log_entries_priority",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'deferred', 'skipped')",
            name="ck_orders_log_entries_status",
        ),
        Index("idx_orders_log_time", "game_id", "game_day", "game_part"),
        Index("idx_orders_log_status", "status"),
        Index("idx_orders_log_commander", "related_commander_id"),
    )

    def __repr__(self) -> str:
        return f"<OrdersLogEntry(id={self.id}, type='{self.entry_type}', day={self.game_day}, status='{self.status}')>"
