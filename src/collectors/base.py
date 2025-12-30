"""Abstract base collector for SofaScore data collection."""

from abc import ABC, abstractmethod
import asyncio
import logging
import random
from playwright.async_api import Page

from src.browser.manager import BrowserManager
from src.browser.interceptor import ResponseInterceptor
from src.browser.ws_interceptor import WebSocketInterceptor
from src.config import settings

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for all SofaScore data collectors.

    Provides common functionality for:
    - Browser management
    - Navigation with rate limiting
    - Response and WebSocket interception
    - Error handling and retry logic
    """

    def __init__(
        self,
        browser_manager: BrowserManager,
        sport: str | None = None,
        context_name: str | None = None,
    ):
        """
        Initialize base collector.

        Args:
            browser_manager: BrowserManager instance for browser operations
            sport: Sport to collect data for (football, tennis, etc.)
            context_name: Browser context identifier (defaults to sport name)
        """
        self.browser_manager = browser_manager
        self.sport = sport
        self.context_name = context_name or sport or "default"
        self.page: Page | None = None
        self.http_interceptor: ResponseInterceptor | None = None
        self.ws_interceptor: WebSocketInterceptor | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def collect(self) -> None:
        """
        Main collection logic (to be implemented by subclasses).

        This method contains the core data collection algorithm.
        It should handle navigation, interception setup, and data processing.
        """
        pass

    async def start(self) -> None:
        """Start the collector."""
        if self._running:
            logger.warning(f"Collector '{self.context_name}' is already running")
            return

        logger.info(f"Starting collector: {self.context_name}")
        self._running = True
        self._task = asyncio.create_task(self._run_with_error_handling())

    async def stop(self) -> None:
        """Stop the collector gracefully."""
        if not self._running:
            logger.warning(f"Collector '{self.context_name}' is not running")
            return

        logger.info(f"Stopping collector: {self.context_name}")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug(f"Collector '{self.context_name}' task cancelled")

        await self.cleanup()
        logger.info(f"Collector '{self.context_name}' stopped")

    async def _run_with_error_handling(self) -> None:
        """Run collector with error handling and retry logic."""
        retry_count = 0
        max_retries = 5
        base_delay = 5

        while self._running:
            try:
                await self.setup()
                await self.collect()
                # If collect() completes without error, reset retry count
                retry_count = 0
            except asyncio.CancelledError:
                logger.info(f"Collector '{self.context_name}' cancelled")
                raise
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"Error in collector '{self.context_name}': {e}",
                    exc_info=True,
                )

                if retry_count >= max_retries:
                    logger.error(
                        f"Max retries ({max_retries}) reached for '{self.context_name}'. Stopping."
                    )
                    self._running = False
                    break

                # Exponential backoff with jitter
                delay = min(base_delay * (2**retry_count), 300) + random.uniform(0, 5)
                logger.info(
                    f"Retrying '{self.context_name}' in {delay:.1f}s (attempt {retry_count}/{max_retries})"
                )
                await asyncio.sleep(delay)

    async def setup(self) -> None:
        """Setup browser page and interceptors."""
        logger.debug(f"Setting up collector: {self.context_name}")

        # Create new page
        self.page = await self.browser_manager.new_page(self.context_name)

        # Setup HTTP interceptor
        from src.browser.interceptor import create_interceptor

        self.http_interceptor = await create_interceptor(self.page)

        # Setup WebSocket interceptor
        from src.browser.ws_interceptor import create_ws_interceptor

        self.ws_interceptor = await create_ws_interceptor(self.page)

        logger.debug(f"Collector '{self.context_name}' setup complete")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.debug(f"Cleaning up collector: {self.context_name}")

        if self.http_interceptor:
            self.http_interceptor.clear_handlers()

        if self.ws_interceptor:
            self.ws_interceptor.clear_handlers()

        if self.page and not self.page.is_closed():
            await self.page.close()
            self.page = None

        logger.debug(f"Collector '{self.context_name}' cleanup complete")

    async def navigate_with_delay(
        self, url: str, wait_until: str = "networkidle"
    ) -> None:
        """
        Navigate to URL with rate limiting delay.

        Args:
            url: URL to navigate to
            wait_until: Wait strategy ('load', 'domcontentloaded', 'networkidle')

        Raises:
            RuntimeError: If page is not initialized
        """
        if not self.page:
            raise RuntimeError("Page not initialized. Call setup() first.")

        # Random delay to simulate human behavior
        delay = random.uniform(
            settings.navigation_delay_min, settings.navigation_delay_max
        )
        logger.debug(f"Waiting {delay:.1f}s before navigation (rate limiting)")
        await asyncio.sleep(delay)

        # Navigate
        logger.info(f"Navigating to: {url}")
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=60000)
            logger.debug(f"Navigation complete: {url}")
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            raise

    async def wait_for_data(self, timeout: float = 10.0) -> None:
        """
        Wait for data to be intercepted.

        Useful after navigation to ensure API responses are captured.

        Args:
            timeout: Maximum time to wait in seconds
        """
        logger.debug(f"Waiting up to {timeout}s for data interception")
        await asyncio.sleep(timeout)

    def is_running(self) -> bool:
        """Check if collector is currently running."""
        return self._running

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False
