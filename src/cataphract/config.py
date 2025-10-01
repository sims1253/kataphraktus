"""Configuration management for the Cataphract application.

This module provides configuration settings using pydantic-settings,
supporting environment variables and default values.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings.

    Attributes:
        DATABASE_URL: Database connection string (SQLite by default)
        DATABASE_ECHO: Whether to echo SQL statements (for debugging)
        DATABASE_POOL_SIZE: Connection pool size for SQLite
        DATABASE_MAX_OVERFLOW: Maximum overflow connections
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database settings
    DATABASE_URL: str = Field(
        default="sqlite:///./cataphract.db",
        description="Database connection URL",
    )

    DATABASE_ECHO: bool = Field(
        default=False,
        description="Echo SQL statements to console",
    )

    DATABASE_POOL_SIZE: int = Field(
        default=5,
        description="Database connection pool size",
        ge=1,
        le=20,
    )

    DATABASE_MAX_OVERFLOW: int = Field(
        default=10,
        description="Maximum overflow connections",
        ge=0,
        le=20,
    )

    DATABASE_POOL_RECYCLE: int = Field(
        default=1800,
        description="Recycle connections after N seconds (helps avoid stale connections)",
        ge=0,
    )

    DATABASE_POOL_TIMEOUT: int = Field(
        default=30,
        description="Maximum seconds to wait for a connection from the pool",
        ge=0,
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate and normalize database URL.

        Args:
            v: The database URL to validate

        Returns:
            str: The validated and normalized database URL

        Raises:
            ValueError: If the URL is invalid
        """
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")

        # For SQLite, ensure the directory exists
        if v.startswith("sqlite:///"):
            db_path = v.replace("sqlite:///", "")
            if db_path and db_path != ":memory:":
                # Create parent directory if it doesn't exist
                db_file = Path(db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)

        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings singleton

    Note:
        This function is cached to ensure we use a single settings
        instance throughout the application lifecycle.
    """
    return Settings()
