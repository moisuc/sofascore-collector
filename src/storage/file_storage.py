"""File-based storage for intercepted API responses."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Manages file-based storage of intercepted API responses.

    Saves raw JSON responses to disk with pattern-based naming.
    Provides automatic cleanup of old files.
    """

    def __init__(self, base_path: Path | str = Path("data/files")):
        """
        Initialize file storage service.

        Args:
            base_path: Base directory for file storage (default: data/files)
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._cleanup_task: asyncio.Task | None = None
        logger.info(f"FileStorageService initialized at {self.base_path.absolute()}")

    def save_response(
        self,
        pattern_name: str,
        sport: str,
        date_str: str | None,
        data: dict,
    ) -> Path:
        """
        Save API response to JSON file with metadata.

        Filename format: {pattern}_{sport}_{date}.json
        Files with same name are overwritten (latest data wins).

        Args:
            pattern_name: API pattern name (live, scheduled, featured, inverse)
            sport: Sport name (football, tennis, etc)
            date_str: Date string (YYYY_MM_DD format), or None to use current date
            data: JSON data to save

        Returns:
            Path to saved file

        Example:
            >>> service.save_response("scheduled", "football", "2025_01_12", {...})
            Path("data/files/scheduled_football_2025_01_12.json")
        """
        # Use current date if not provided
        if date_str is None:
            date_str = datetime.now().strftime("%Y_%m_%d")

        # Generate filename
        filename = f"{pattern_name}_{sport}_{date_str}.json"
        file_path = self.base_path / filename

        # Wrap data with metadata
        output = {
            "metadata": {
                "source": "sofascore",
                "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "type": sport,
            },
            "data": data,
        }

        try:
            # Write JSON to file (overwrites existing)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved response to {filename}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save response to {filename}: {e}", exc_info=True)
            raise

    def cleanup_old_files(self, max_age_days: int = 10) -> int:
        """
        Delete files older than specified age.

        Args:
            max_age_days: Maximum file age in days (default: 10)

        Returns:
            Number of files deleted
        """
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0

        try:
            for file_path in self.base_path.glob("*.json"):
                if not file_path.is_file():
                    continue

                # Check file modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                if mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path.name}: {e}")

            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} files older than {max_age_days} days"
                )

            return deleted_count

        except Exception as e:
            logger.error(f"Error during file cleanup: {e}", exc_info=True)
            return deleted_count

    async def start_cleanup_task(
        self,
        interval_seconds: int = 3600,
        max_age_days: int = 10,
    ) -> None:
        """
        Start background task for periodic file cleanup.

        Runs cleanup on startup and then periodically at specified interval.

        Args:
            interval_seconds: Seconds between cleanup runs (default: 3600 = 1 hour)
            max_age_days: Maximum file age in days (default: 10)
        """
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return

        async def cleanup_loop():
            # Run cleanup on startup
            logger.info(f"Running initial file cleanup (max_age: {max_age_days} days)")
            await asyncio.to_thread(self.cleanup_old_files, max_age_days)

            # Periodic cleanup
            while True:
                await asyncio.sleep(interval_seconds)
                logger.debug("Running scheduled file cleanup")
                await asyncio.to_thread(self.cleanup_old_files, max_age_days)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(
            f"File cleanup task started (interval: {interval_seconds}s, max_age: {max_age_days} days)"
        )

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("File cleanup task stopped")
