"""Browser pool management for Playwright automation."""

import asyncio
import logging
import os
from pathlib import Path

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

logger = logging.getLogger(__name__)

# Browser state persistence file (cookies + localStorage)
STORAGE_STATE_PATH = Path("data/browser_state.json")


class BrowserManager:
    """
    Manages Playwright browser instances and contexts.

    Provides browser pool management with isolated contexts per sport
    and automatic refresh capabilities to maintain active connections.
    """

    def __init__(self, headless: bool = True):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.headless = headless
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.contexts: dict[str, BrowserContext] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}
        self._cleanup_task: asyncio.Task | None = None  # Periodic cleanup task

    async def start(self) -> None:
        """Start Playwright and launch browser."""
        logger.info("Starting browser manager...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        logger.info("Browser launched successfully")

    async def create_context(self, name: str = "default") -> BrowserContext:
        """
        Create a new browser context (isolated browsing session).

        Args:
            name: Unique identifier for this context (e.g., sport name)

        Returns:
            BrowserContext instance
        """
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first.")

        if name in self.contexts:
            logger.warning(
                f"Context '{name}' already exists, returning existing context"
            )
            return self.contexts[name]

        logger.info(f"Creating browser context: {name}")

        # Load browser state if file exists
        storage_state = None
        if STORAGE_STATE_PATH.exists():
            storage_state = str(STORAGE_STATE_PATH)
            logger.info(f"Loading browser state from {STORAGE_STATE_PATH}")

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Europe/London",
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
            storage_state=storage_state,
        )
        self.contexts[name] = context
        logger.info(f"Context '{name}' created successfully")
        return context

    async def get_context(self, name: str) -> BrowserContext | None:
        """
        Get existing context by name.

        Args:
            name: Context identifier

        Returns:
            BrowserContext if exists, None otherwise
        """
        return self.contexts.get(name)

    async def new_page(self, context_name: str = "default") -> Page:
        """
        Create a new page in the specified context.

        Args:
            context_name: Name of the context to create page in

        Returns:
            Page instance
        """
        context = self.contexts.get(context_name)
        if not context:
            context = await self.create_context(context_name)

        page = await context.new_page()
        logger.debug(f"New page created in context '{context_name}'")
        return page

    async def refresh_page_periodically(
        self, page: Page, interval: int = 300, context_name: str = "default"
    ) -> None:
        """
        Refresh a page periodically to maintain connection.

        Args:
            page: Page to refresh
            interval: Refresh interval in seconds (default: 5 minutes)
            context_name: Context identifier for task management
        """
        task_key = f"{context_name}_refresh"

        async def refresh_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    logger.debug(f"Refreshing page in context '{context_name}'")
                    await page.reload(wait_until="networkidle")
                    logger.debug("Page refreshed successfully")
                except Exception as e:
                    logger.error(
                        f"Error refreshing page in context '{context_name}': {e}"
                    )
                    break

        task = asyncio.create_task(refresh_loop())
        self._refresh_tasks[task_key] = task
        logger.info(
            f"Started periodic refresh for context '{context_name}' (interval: {interval}s)"
        )

    async def stop_refresh(self, context_name: str) -> None:
        """
        Stop periodic refresh for a context.

        Args:
            context_name: Context identifier
        """
        task_key = f"{context_name}_refresh"
        if task_key in self._refresh_tasks:
            self._refresh_tasks[task_key].cancel()
            try:
                await self._refresh_tasks[task_key]
            except asyncio.CancelledError:
                pass
            del self._refresh_tasks[task_key]
            logger.info(f"Stopped periodic refresh for context '{context_name}'")

    async def close_context(self, name: str) -> None:
        """
        Close and remove a specific context.

        Args:
            name: Context identifier
        """
        await self.stop_refresh(name)

        if name in self.contexts:
            logger.info(f"Closing context: {name}")
            await self.contexts[name].close()
            del self.contexts[name]
            logger.info(f"Context '{name}' closed")

    async def clear_browser_cache(self, preserve_cookies: bool = True) -> None:
        """
        Clear browser cache for all contexts.

        Note: Playwright doesn't expose direct cache clearing APIs.
        This implementation clears storage except cookies to preserve sessions.

        Args:
            preserve_cookies: If True, preserve cookies to maintain sessions
        """
        logger.info(f"Clearing browser cache (preserve_cookies={preserve_cookies})")

        for context_name, context in list(self.contexts.items()):
            try:
                # Get all pages in context
                pages = context.pages

                if pages:
                    for page in pages:
                        try:
                            # Clear storage via JavaScript (preserves cookies if requested)
                            if preserve_cookies:
                                # Clear only localStorage and sessionStorage
                                await page.evaluate("""
                                    () => {
                                        localStorage.clear();
                                        sessionStorage.clear();
                                    }
                                """)
                            else:
                                # Clear everything including cookies
                                await page.evaluate("""
                                    () => {
                                        localStorage.clear();
                                        sessionStorage.clear();
                                    }
                                """)
                                await context.clear_cookies()

                            logger.debug(f"Cleared cache for page in context '{context_name}'")

                        except Exception as e:
                            logger.warning(f"Error clearing cache for page: {e}")

                else:
                    logger.debug(f"No pages in context '{context_name}' to clear cache")

            except Exception as e:
                logger.error(f"Error clearing cache for context '{context_name}': {e}")

        # Force garbage collection
        import gc
        collected = gc.collect()
        logger.debug(f"Garbage collection freed {collected} objects")

        logger.info("Browser cache clearing complete")

    async def schedule_periodic_cleanup(self, interval: int = 3600) -> None:
        """
        Schedule periodic browser cache cleanup.

        Args:
            interval: Cleanup interval in seconds (default: 1 hour)
        """
        if self._cleanup_task:
            logger.warning("Periodic cleanup already scheduled")
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    logger.info("Running scheduled browser cache cleanup")
                    await self.clear_browser_cache(preserve_cookies=True)
                except Exception as e:
                    logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
                    break

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Scheduled periodic browser cleanup (interval: {interval}s)")

    async def stop_periodic_cleanup(self) -> None:
        """Stop periodic browser cache cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped periodic browser cleanup")

    async def shutdown(self) -> None:
        """Shutdown all contexts and browser."""
        logger.info("Shutting down browser manager...")

        # Stop periodic cleanup task
        await self.stop_periodic_cleanup()

        # Stop all refresh tasks
        for task_key in list(self._refresh_tasks.keys()):
            context_name = task_key.replace("_refresh", "")
            await self.stop_refresh(context_name)

        # Save browser state before closing contexts
        if self.contexts:
            try:
                # Save state from first available context
                first_context = next(iter(self.contexts.values()))
                # Ensure data directory exists
                STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Saving browser state to {STORAGE_STATE_PATH}")
                await first_context.storage_state(path=str(STORAGE_STATE_PATH))
                logger.info("Browser state saved successfully")
            except Exception as e:
                logger.error(f"Failed to save browser state: {e}")
                # Continue with shutdown even if save fails

        # Close all contexts
        for name in list(self.contexts.keys()):
            await self.contexts[name].close()
        self.contexts.clear()

        # Close browser and playwright
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("Browser manager shutdown complete")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()
        return False
