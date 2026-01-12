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
    enable_ws_interceptor: bool = False  # Enable/disable WebSocket interceptor

    # Database settings
    database_url: str = "sqlite:///data/sofascore.db"

    # Redis settings (optional)
    redis_url: str | None = None

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Sports to track
    sports: list[str] = ["football", "tennis", "basketball", "handball", "volleyball", "ice-hockey"]

    # Rate limiting
    navigation_delay_min: int = 2
    navigation_delay_max: int = 5
    page_refresh_interval: int = 300  # 5 minutes in seconds
    backfill_delay: int = 10  # seconds between backfill requests

    # UI interaction
    click_show_all: bool = True  # Automatically click "Show all" buttons after page load
    show_all_wait_after: float = 3.0  # Seconds to wait after clicking for content to expand

    # Memory Management
    max_db_sessions: int = 10  # Maximum database sessions in pool
    min_db_sessions: int = 2  # Minimum sessions to keep in pool
    session_idle_timeout: float = 300.0  # Session idle timeout in seconds (5 min)
    session_acquire_timeout: float = 30.0  # Max wait time for session acquisition

    max_contexts_per_sport: int = 2  # Max browser contexts per sport
    context_idle_timeout: float = 600.0  # Context idle timeout in seconds (10 min)

    max_queue_size: int = 1000  # Maximum size for interceptor queues

    cleanup_interval: float = 60.0  # Run cleanup every N seconds

    memory_warning_threshold: float = 0.8  # Warn at 80% memory usage
    memory_critical_threshold: float = 0.95  # Critical at 95% memory usage

    # Memory Management (new)
    memory_check_interval: float = 30.0  # Check memory every N seconds
    memory_limit_mb: int = 4096  # Memory threshold in MB (triggers cleanup at 90%)
    memory_target_percent: float = 0.5  # Target 50% usage after cleanup
    chrome_cleanup_interval: int = 3600  # Chrome cleanup interval (1 hour)
    memory_metrics_file: str = "data/memory_metrics.json"  # Metrics file path

    # File Storage settings
    file_storage_enabled: bool = True  # Enable/disable file-based storage
    file_storage_base_path: str = "data/files"  # Base directory for JSON files
    file_storage_max_age_days: int = 10  # Delete files older than N days
    file_storage_cleanup_interval: int = 3600  # Cleanup interval in seconds (1 hour)

    # API settings
    api_root_path: str = ""  # Root path for reverse proxy (e.g., /python/sofascore-collector/src/api)


# Global settings instance
settings = Settings()
