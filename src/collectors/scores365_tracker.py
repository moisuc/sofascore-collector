"""Live tracker that captures raw 365scores ``webws`` traffic.

Stays on a 365scores scores page (which polls ``webws.365scores.com`` for live
updates via a ``lastUpdateId`` cursor) and persists every intercepted
``allscores``/``current`` response raw to disk. Refreshes periodically to keep
traffic flowing and as a fallback data source.
"""

import asyncio
import logging

from src.browser.manager import BrowserManager
from src.browser.scores365_interceptor import (
    Scores365Interceptor,
    extract_url_params,
)
from src.collectors.base import BaseCollector
from src.config import settings
from src.storage.scores365_storage import Scores365FileStorage

logger = logging.getLogger(__name__)


class Scores365Tracker(BaseCollector):
    """Capture and save raw 365scores ``webws`` responses continuously."""

    def __init__(self, browser_manager: BrowserManager):
        super().__init__(browser_manager, sport=None, context_name="scores365")
        self.url = settings.scores365_url
        self.interceptor: Scores365Interceptor | None = None
        self.storage = Scores365FileStorage(settings.scores365_storage_path)
        self._refresh_task: asyncio.Task | None = None

    async def setup(self) -> None:
        """Create the page and attach the 365scores interceptor.

        Intentionally does NOT call ``super().setup()`` to avoid wiring the
        SofaScore HTTP interceptor / header capture / direct fetch.
        """
        logger.debug("Setting up 365scores tracker")
        self.page = await self.browser_manager.new_page(self.context_name)

        self.interceptor = Scores365Interceptor(self.page)
        await self.interceptor.attach(self.page)
        self.interceptor.on("allscores", self._handle_capture)
        self.interceptor.on("current", self._handle_capture)
        logger.debug("365scores tracker setup complete")

    async def collect(self) -> None:
        """Navigate to the 365scores page and keep capturing updates."""
        logger.info("Starting 365scores tracker")

        await self.navigate_with_delay(self.url, wait_until="networkidle")
        await self._handle_consent(timeout=5.0)

        # Let initial allscores/current calls land.
        await self.wait_for_data(timeout=5.0)
        logger.info("365scores initial data captured")

        self._refresh_task = asyncio.create_task(self._periodic_refresh())

        try:
            while self._running:
                await asyncio.sleep(60)
                logger.debug("365scores tracker still active")
        except asyncio.CancelledError:
            logger.info("365scores tracker cancelled")
            raise
        finally:
            if self._refresh_task:
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass

    async def _handle_capture(self, data: dict, endpoint: str, url: str) -> None:
        """Persist a captured response raw to disk."""
        try:
            params = extract_url_params(url)
            path = self.storage.save_response(endpoint, data, url, params)
            logger.info(f"Saved 365scores {endpoint} capture: {path.name}")
        except Exception as e:
            logger.error(f"Failed to save 365scores {endpoint} capture: {e}", exc_info=True)

    async def _periodic_refresh(self) -> None:
        """Reload the page periodically to force fresh full snapshots."""
        interval = settings.scores365_refresh_interval
        logger.info(f"Starting 365scores periodic refresh (interval: {interval}s)")

        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self.page or self.page.is_closed():
                    logger.warning("365scores page closed, stopping refresh task")
                    break
                logger.debug("Refreshing 365scores page")
                await self.page.reload(wait_until="networkidle", timeout=60000)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error refreshing 365scores page: {e}")

    async def _handle_consent(self, timeout: float = 5.0) -> bool:
        """Best-effort dismiss of the 365scores cookie/consent dialog.

        365scores uses a TCF/CMP consent banner whose markup differs from
        SofaScore's. Tries a few common accept selectors; non-fatal on miss.
        """
        if not self.page:
            return False

        selectors = [
            "#onetrust-accept-btn-handler",
            'button[aria-label="Accept all"]',
            'button:has-text("AGREE")',
            'button:has-text("Accept")',
            'button:has-text("Accept all")',
        ]
        for selector in selectors:
            try:
                button = self.page.locator(selector).first
                await button.wait_for(state="visible", timeout=timeout * 1000)
                await button.click()
                logger.info(f"365scores consent dismissed via '{selector}'")
                await asyncio.sleep(1.0)
                return True
            except Exception:
                continue

        logger.debug("No 365scores consent dialog handled")
        return False

    async def cleanup(self) -> None:
        """Cleanup interceptor, refresh task and page."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self.interceptor:
            self.interceptor.clear_handlers()

        if self.page and not self.page.is_closed():
            await self.page.close()
            self.page = None

        logger.debug("365scores tracker cleanup complete")


async def create_scores365_tracker(browser_manager: BrowserManager) -> Scores365Tracker:
    """Create and start a 365scores tracker."""
    tracker = Scores365Tracker(browser_manager)
    await tracker.start()
    return tracker
