from datetime import date

from pydantic import BaseModel, Field


class GameCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Unique name for this game campaign")
    start_date: date = Field(..., description="Real-world date when the game started")
    current_day: int = Field(default=0, ge=0, description="Current in-game day (0-indexed)")
    current_day_part: str = Field(
        default="morning", description="Current daypart (morning/midday/evening/night)"
    )
    tick_schedule: str = Field(
        default="daily", description="How often the game ticks (daily or 4x per day)"
    )
    map_width: int = Field(..., gt=0, description="Width of the hex map")
    map_height: int = Field(..., gt=0, description="Height of the hex map")
    season: str = Field(..., description="Current season affecting weather and movement")
    status: str = Field(
        default="setup", description="Current game state (setup/active/paused/completed)"
    )


class GameRead(GameCreate):
    id: int = Field(..., description="Primary key")


class GameUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    start_date: date | None = None
    current_day: int | None = Field(None, ge=0)
    current_day_part: str | None = None
    tick_schedule: str | None = None
    map_width: int | None = Field(None, gt=0)
    map_height: int | None = Field(None, gt=0)
    season: str | None = None
    status: str | None = None
