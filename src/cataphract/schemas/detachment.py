from typing import Any

from pydantic import BaseModel, Field


class DetachmentCreate(BaseModel):
    army_id: int = Field(..., description="Foreign key to army")
    unit_type_id: int = Field(..., description="Foreign key to unit type")
    name: str = Field(..., min_length=1, description="Name of the detachment")
    soldier_count: int = Field(..., ge=0, description="Number of soldiers (0 for siege_engines)")
    wagon_count: int = Field(default=0, ge=0, description="Number of wagons")
    engine_count: int | None = Field(
        None, ge=0, description="Number of siege engines (for siege_engines unit type)"
    )
    region_of_origin: str | None = Field(
        None, description="Region where this detachment was recruited"
    )
    formation_position: int = Field(..., ge=0, description="Position in army formation")
    honors: list[str] | None = Field(None, description="JSON array of earned honors/titles")
    instance_data: dict[str, Any] | None = Field(None, description="JSON for unit-specific state")


class DetachmentRead(DetachmentCreate):
    id: int = Field(..., description="Primary key")
