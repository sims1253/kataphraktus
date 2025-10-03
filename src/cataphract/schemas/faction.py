from typing import Any

from pydantic import BaseModel, Field


class FactionCreate(BaseModel):
    game_id: int = Field(..., description="Foreign key to game")
    name: str = Field(..., min_length=1, description="Name of the faction")
    description: str | None = Field(None, description="Description of the faction")
    color: str = Field(..., description="Hex color code for map display")
    special_rules: dict[str, Any] | None = Field(
        None, description="JSON object with faction-specific rules"
    )
    unique_units: list[str] | None = Field(None, description="JSON array of unique unit type names")


class FactionRead(FactionCreate):
    id: int = Field(..., description="Primary key")
