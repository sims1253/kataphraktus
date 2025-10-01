"""Weather model for the Cataphract game system.

This module contains the model for weather conditions that affect
movement, scouting, and other game mechanics.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .game import Game


class Weather(Base):
    """Represents weather conditions for a specific game day.

    Weather affects movement speed, scouting range, and other mechanics.
    Different weather types have different effects.

    Attributes:
        id: Primary key
        game_id: Foreign key to game
        game_day: Game day for this weather
        weather_type: Type of weather (clear/rain/snow/storm/fog/very_bad)
        effects: JSON object with effects (movement/scouting modifiers, etc)
    """

    __tablename__ = "weather"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)

    # Weather attributes
    game_day: Mapped[int] = mapped_column(Integer, nullable=False)
    weather_type: Mapped[str] = mapped_column(String, nullable=False)
    effects: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="weather")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("game_id", "game_day", name="uq_weather_game_day"),
        CheckConstraint(
            "weather_type IN ('clear', 'rain', 'snow', 'storm', 'fog', 'very_bad')",
            name="ck_weather_type",
        ),
        Index("idx_weather_day", "game_id", "game_day"),
    )

    def __repr__(self) -> str:
        return f"<Weather(id={self.id}, day={self.game_day}, type='{self.weather_type}')>"
