from pydantic import BaseModel, Field


class CommanderCreate(BaseModel):
    game_id: int = Field(..., description="Foreign key to game")
    player_id: int | None = Field(
        None, description="Foreign key to player controlling this commander"
    )
    faction_id: int = Field(..., description="Foreign key to faction this commander belongs to")
    name: str = Field(..., min_length=1, description="Name of the commander")
    age: int = Field(..., ge=14, description="Age of the commander (minimum 14)")
    relationship_type: str | None = Field(
        None, description="Type of relationship to another commander"
    )
    related_to_commander_id: int | None = Field(
        None, description="Foreign key to related commander"
    )
    current_hex_id: int | None = Field(
        None, description="Foreign key to hex where commander is located"
    )
    status: str = Field(default="active", description="Current status (active/captured/dead)")
    captured_by_faction_id: int | None = Field(
        None, description="Faction that captured this commander (if captured)"
    )


class CommanderRead(CommanderCreate):
    id: int = Field(..., description="Primary key")
