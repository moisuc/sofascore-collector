"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Browser settings
    headless: bool = True

    # Database settings
    database_url: str = "sqlite:///data/sofascore.db"

    # Redis settings (optional)
    redis_url: str | None = None

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Sports to track
    sports: list[str] = ["football", "tennis", "basketball", "handball", "volleyball"]

    # Rate limiting
    navigation_delay_min: int = 2
    navigation_delay_max: int = 5
    page_refresh_interval: int = 300  # 5 minutes in seconds
    backfill_delay: int = 10  # seconds between backfill requests


# Global settings instance
settings = Settings()
