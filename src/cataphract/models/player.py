"""Player model for the Cataphract game system.

This module contains the model for players (users of the system),
including authentication credentials and role information.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampCreatedMixin

if TYPE_CHECKING:
    from .commander import Commander


class Player(Base, TimestampCreatedMixin):
    """Represents a player/user of the system.

    Players can control commanders in games and may have referee privileges
    to manage games.

    Attributes:
        id: Primary key
        username: Unique username
        email: Unique email address
        password_hash: Hashed password (use passlib for hashing)
        is_referee: Whether this player has referee privileges
        last_login: Timestamp of last login
    """

    __tablename__ = "players"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Authentication
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_referee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    commanders: Mapped[list["Commander"]] = relationship("Commander", back_populates="player")

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username='{self.username}', is_referee={self.is_referee})>"
