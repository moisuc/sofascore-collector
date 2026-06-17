"""Raw file storage for intercepted 365scores ``webws`` responses.

Each captured response is written to its own file (never overwritten) so the
full incremental update stream is preserved. 365scores' ``allscores``/``current``
endpoints poll with a ``lastUpdateId`` cursor, so consecutive captures differ;
overwriting by date (as the SofaScore :class:`FileStorageService` does) would
drop intermediate updates.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Characters not safe for filenames are collapsed to ``_``.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(value: str) -> str:
    return _UNSAFE.sub("_", value).strip("_") or "na"


class Scores365FileStorage:
    """Persist raw 365scores responses to unique per-capture JSON files.

    Filename format: ``{endpoint}_sports{sports}_{YYYYmmdd_HHMMSSfff}_{lastUpdateId}.json``
    """

    def __init__(self, base_path: Path | str = Path("data/files/365scores")):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._cleanup_task: asyncio.Task | None = None
        logger.info(f"Scores365FileStorage initialized at {self.base_path.absolute()}")

    def save_response(
        self,
        endpoint: str,
        data: dict,
        url: str,
        params: dict[str, str] | None = None,
    ) -> Path:
        """Write a captured response to a unique file with metadata.

        Args:
            endpoint: Short endpoint name (``allscores``/``current``).
            data: Parsed JSON payload.
            url: Full request URL (stored in metadata).
            params: Query params extracted from the URL (used for naming/metadata).

        Returns:
            Path to the written file.
        """
        params = params or {}
        sports = params.get("sports", "all")
        # Prefer the cursor from the payload; fall back to the URL param.
        last_update_id = str(data.get("lastUpdateId") or params.get("lastUpdateId") or "na")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
        filename = (
            f"{_safe(endpoint)}_sports{_safe(str(sports))}_"
            f"{timestamp}_{_safe(last_update_id)}.json"
        )
        file_path = self.base_path / filename

        output = {
            "metadata": {
                "source": "365scores",
                "endpoint": endpoint,
                "url": url,
                "params": params,
                "last_update_id": last_update_id,
                "captured_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            },
            "data": data,
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved 365scores response to {filename}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save 365scores response {filename}: {e}", exc_info=True)
            raise

    def cleanup_old_files(self, max_age_days: int = 10) -> int:
        """Delete files older than ``max_age_days``. Returns count deleted."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        deleted = 0
        try:
            for file_path in self.base_path.glob("*.json"):
                if not file_path.is_file():
                    continue
                if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path.name}: {e}")
            if deleted:
                logger.info(f"Cleaned up {deleted} 365scores files older than {max_age_days} days")
            return deleted
        except Exception as e:
            logger.error(f"Error during 365scores file cleanup: {e}", exc_info=True)
            return deleted

    async def start_cleanup_task(
        self, interval_seconds: int = 3600, max_age_days: int = 10
    ) -> None:
        """Start a background task that prunes old files periodically."""
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("365scores cleanup task already running")
            return

        async def cleanup_loop():
            await asyncio.to_thread(self.cleanup_old_files, max_age_days)
            while True:
                await asyncio.sleep(interval_seconds)
                await asyncio.to_thread(self.cleanup_old_files, max_age_days)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(
            f"365scores cleanup task started "
            f"(interval: {interval_seconds}s, max_age: {max_age_days} days)"
        )

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("365scores cleanup task stopped")
