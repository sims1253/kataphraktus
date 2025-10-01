"""Game model for the Cataphract game system.

The Game model represents a single instance of a Cataphract campaign,
tracking its state, timing, and map configuration.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .army import Army
    from .commander import Commander
    from .event import Event
    from .faction import Faction
    from .map import Hex
    from .message import Message
    from .order import Order
    from .weather import Weather


class Game(Base, TimestampMixin):
    """Represents a single Cataphract game campaign.

    A game encompasses all the entities, state, and history for one instance
    of the Cataphract strategic wargame. It tracks the current game time
    (both day and daypart), map dimensions, season, and overall game status.

    Attributes:
        id: Primary key
        name: Unique name for this game campaign
        start_date: Real-world date when the game started
        current_day: Current in-game day (0-indexed)
        current_day_part: Current daypart (morning/midday/evening/night)
        tick_schedule: How often the game ticks (daily or 4x per day)
        map_width: Width of the hex map
        map_height: Height of the hex map
        season: Current season affecting weather and movement
        status: Current game state (setup/active/paused/completed)
    """

    __tablename__ = "games"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Basic game info
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Game time tracking
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_day_part: Mapped[str] = mapped_column(String, nullable=False, default="morning")
    tick_schedule: Mapped[str] = mapped_column(String, nullable=False, default="daily")

    # Map configuration
    map_width: Mapped[int] = mapped_column(Integer, nullable=False)
    map_height: Mapped[int] = mapped_column(Integer, nullable=False)

    # Game state
    season: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    hexes: Mapped[list["Hex"]] = relationship(
        "Hex", back_populates="game", cascade="all, delete-orphan"
    )
    factions: Mapped[list["Faction"]] = relationship(
        "Faction", back_populates="game", cascade="all, delete-orphan"
    )
    commanders: Mapped[list["Commander"]] = relationship(
        "Commander", back_populates="game", cascade="all, delete-orphan"
    )
    armies: Mapped[list["Army"]] = relationship(
        "Army", back_populates="game", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="game", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="game", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="game", cascade="all, delete-orphan"
    )
    weather: Mapped[list["Weather"]] = relationship(
        "Weather", back_populates="game", cascade="all, delete-orphan"
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "current_day_part IN ('morning', 'midday', 'evening', 'night')",
            name="ck_games_current_day_part",
        ),
        CheckConstraint(
            "season IN ('spring', 'summer', 'fall', 'winter')",
            name="ck_games_season",
        ),
        CheckConstraint(
            "status IN ('setup', 'active', 'paused', 'completed')",
            name="ck_games_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, name='{self.name}', day={self.current_day}, status='{self.status}')>"
