"""Lightweight configuration for the Cataphract tools."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Minimal application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    data_dir: Path = Field(default=Path("campaigns"), description="Where campaign snapshots live")
    rules_version: str = Field(default="1.1", description="Ruleset version used by the domain")
    tick_interval_seconds: float = Field(
        default=300.0,
        description="Real-time seconds between automatic ticks when scheduling is enabled",
        gt=0.0,
    )
    debug_tick_speed_multiplier: float = Field(
        default=1.0,
        description="Multiplier applied to the tick interval to speed up or slow down ticks in development",
        gt=0.0,
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Origins allowed to call the HTTP API",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
