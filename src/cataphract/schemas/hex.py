from pydantic import BaseModel, Field


class HexRead(BaseModel):
    id: int = Field(..., description="Primary key")
    game_id: int = Field(..., description="Foreign key to game")
    q: int = Field(..., description="Axial coordinate q")
    r: int = Field(..., description="Axial coordinate r")
    terrain_type: str = Field(
        ..., description="Type of terrain (flatland/hills/forest/mountain/water/coast)"
    )
    is_good_country: bool = Field(
        default=False, description="Whether this is good country (better foraging)"
    )
    has_road: bool = Field(
        default=False, description="Denormalized UI flag (road_edges is source of truth)"
    )
    settlement_score: int | None = Field(None, description="Economic value (0/20/40/60/80/100)")
    river_sides: list[str] | None = Field(
        None, description='JSON array of hex edges with rivers (e.g., ["NE", "E"])'
    )
    foraging_times_remaining: int = Field(
        default=5, ge=0, description="How many more times hex can be foraged"
    )
    is_torched: bool = Field(default=False, description="Whether hex has been torched")
    last_foraged_day: int | None = Field(
        None, description="Game day when last foraged (for revolt rules)"
    )
    last_recruited_day: int | None = Field(
        None, description="Game day when last recruited (for revolt rules)"
    )
    last_torched_day: int | None = Field(
        None, description="Game day when last torched (for revolt rules)"
    )
    controlling_faction_id: int | None = Field(
        None, description="Faction that controls this hex (NULL if unclaimed)"
    )
    last_control_change_day: int | None = Field(
        None, description="Game day when control last changed"
    )
