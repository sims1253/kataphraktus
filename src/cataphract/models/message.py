"""Message models for the Cataphract game system.

This module contains models for:
- Messages (communications between commanders)
- MessageLegs (normalized route segments for messages)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .commander import Commander
    from .game import Game
    from .map import Hex


class Message(Base, TimestampCreatedMixin):
    """Represents a message sent between commanders.

    Messages take time to travel based on distance and territory control.
    They can be intercepted in hostile territory.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        sender_commander_id: Foreign key to sending commander
        recipient_commander_id: Foreign key to receiving commander
        content: Content of the message
        sent_at_day: Game day when sent
        sent_at_part: Daypart when sent
        sent_at_timestamp: Real-world timestamp when sent
        delivered_at_day: Game day when delivered
        delivered_at_part: Daypart when delivered
        delivered_at_timestamp: Real-world timestamp when delivered
        route_legs: JSON with complete route information
        delivery_success_roll: Deterministic RNG roll for delivery
        status: Message status (in_transit/delivered/intercepted/failed)
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    sender_commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False
    )
    recipient_commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False
    )

    # Message attributes
    content: Mapped[str] = mapped_column(String, nullable=False)
    sent_at_day: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at_part: Mapped[str] = mapped_column(String, nullable=False)
    sent_at_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivered_at_part: Mapped[str | None] = mapped_column(String, nullable=True)
    delivered_at_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    route_legs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    delivery_success_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="messages")
    sender: Mapped["Commander"] = relationship(
        "Commander",
        back_populates="messages_sent",
        foreign_keys=[sender_commander_id],
    )
    recipient: Mapped["Commander"] = relationship(
        "Commander",
        back_populates="messages_received",
        foreign_keys=[recipient_commander_id],
    )
    legs: Mapped[list["MessageLeg"]] = relationship(
        "MessageLeg", back_populates="message", cascade="all, delete-orphan"
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "sent_at_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_messages_sent_at_part",
        ),
        CheckConstraint(
            "delivered_at_part IS NULL OR delivered_at_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_messages_delivered_at_part",
        ),
        CheckConstraint(
            "status IN ('in_transit', 'delivered', 'intercepted', 'failed')",
            name="ck_messages_status",
        ),
        Index("idx_messages_sender", "sender_commander_id"),
        Index("idx_messages_recipient", "recipient_commander_id"),
        Index("idx_messages_status", "status"),
        Index("idx_messages_delivery", "delivered_at_day", "delivered_at_part"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, from={self.sender_commander_id}, to={self.recipient_commander_id}, status='{self.status}')>"


class MessageLeg(Base, TimestampCreatedMixin):
    """Represents a single leg of a message's route.

    Message legs break down a message route into individual hex-to-hex
    segments, allowing for interception queries and tracking.

    Attributes:
        id: Primary key
        message_id: Foreign key to message
        seq: Sequence number of this leg (0, 1, 2, ...)
        from_hex_id: Source hex
        to_hex_id: Destination hex
        control: Territory control (friendly/neutral/hostile)
        miles: Distance in miles
        road: Whether this leg uses a road
        risk: Per-leg failure probability or hazard weight
        eta_day: Predicted arrival game day at this leg's destination
        eta_part: Predicted arrival daypart at this leg's destination
        control_snapshot_day: Game day when route was locked
        control_snapshot_part: Daypart when route was locked
    """

    __tablename__ = "message_legs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    message_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)
    to_hex_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexes.id"), nullable=False)

    # Message leg attributes
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    control: Mapped[str] = mapped_column(String, nullable=False)
    miles: Mapped[float] = mapped_column(nullable=False)
    road: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk: Mapped[float] = mapped_column(nullable=False)
    eta_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_part: Mapped[str | None] = mapped_column(String, nullable=True)
    control_snapshot_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    control_snapshot_part: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="legs")
    from_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[from_hex_id])
    to_hex: Mapped["Hex"] = relationship("Hex", foreign_keys=[to_hex_id])

    # Table constraints
    __table_args__ = (
        UniqueConstraint("message_id", "seq", name="uq_message_legs"),
        CheckConstraint(
            "control IN ('friendly', 'neutral', 'hostile')",
            name="ck_message_legs_control",
        ),
        CheckConstraint(
            "eta_part IS NULL OR eta_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_message_legs_eta_part",
        ),
        CheckConstraint(
            "control_snapshot_part IS NULL OR control_snapshot_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_message_legs_snapshot_part",
        ),
        Index("idx_message_legs_message", "message_id"),
        Index("idx_message_legs_edge", "from_hex_id", "to_hex_id"),
        Index("idx_message_legs_eta", "eta_day", "eta_part"),
    )

    def __repr__(self) -> str:
        return f"<MessageLeg(id={self.id}, message={self.message_id}, seq={self.seq})>"
