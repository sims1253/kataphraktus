from typing import Any

from pydantic import BaseModel, Field


class ArmyCreate(BaseModel):
    game_id: int = Field(..., description="Foreign key to game")
    commander_id: int = Field(..., description="Foreign key to commander leading this army")
    name: str | None = Field(None, description="Name of the army (optional)")
    current_hex_id: int = Field(..., description="Foreign key to current hex location")
    destination_hex_id: int | None = Field(
        None, description="Foreign key to destination hex (if moving)"
    )
    movement_points_remaining: float = Field(
        default=0.0, ge=0.0, description="Remaining movement points"
    )
    morale_current: int = Field(default=9, ge=0, le=12, description="Current morale level")
    morale_resting: int = Field(
        default=9, ge=0, le=12, description="Resting morale (recovers to this)"
    )
    morale_max: int = Field(default=12, ge=0, le=12, description="Maximum morale")
    supplies_current: int = Field(default=0, ge=0, description="Current supplies")
    supplies_capacity: int = Field(default=0, ge=0, description="Maximum supplies capacity")
    daily_supply_consumption: int = Field(default=0, ge=0, description="Supplies consumed per day")
    loot_carried: int = Field(default=0, ge=0, description="Amount of loot carried")
    noncombatant_count: int = Field(default=0, ge=0, description="Number of noncombatants")
    noncombatant_percentage: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Percentage of noncombatants"
    )
    status: str = Field(default="idle", description="Current status (idle/marching/besieging/etc)")
    forced_march_weeks: float = Field(default=0.0, ge=0.0, description="Weeks of forced marching")
    days_without_supplies: int = Field(
        default=0, ge=0, description="Days without adequate supplies"
    )
    days_marched_this_week: int = Field(
        default=0, ge=0, le=7, description="Days marched this week (enforces caps)"
    )
    status_effects: dict[str, Any] | None = Field(
        None, description="JSON object with status effects"
    )
    column_length_miles: float = Field(
        default=0.0, ge=0.0, description="Length of army column in miles"
    )
    rest_duration_days: int | None = Field(None, ge=0, description="Duration of rest period")
    rest_started_day: int | None = Field(None, ge=0, description="Game day when rest started")
    rest_location_stronghold_id: int | None = Field(
        None, description="Stronghold where resting (if applicable)"
    )


class ArmyRead(ArmyCreate):
    id: int = Field(..., description="Primary key")


class ArmyUpdate(BaseModel):
    name: str | None = None
    current_hex_id: int | None = None
    destination_hex_id: int | None = None
    movement_points_remaining: float | None = None
    morale_current: int | None = None
    morale_resting: int | None = None
    morale_max: int | None = None
    supplies_current: int | None = None
    supplies_capacity: int | None = None
    daily_supply_consumption: int | None = None
    loot_carried: int | None = None
    noncombatant_count: int | None = None
    noncombatant_percentage: float | None = None
    status: str | None = None
    forced_march_weeks: float | None = None
    days_without_supplies: int | None = None
    days_marched_this_week: int | None = None
    status_effects: dict[str, Any] | None = None
    column_length_miles: float | None = None
    rest_duration_days: int | None = None
    rest_started_day: int | None = None
    rest_location_stronghold_id: int | None = None
