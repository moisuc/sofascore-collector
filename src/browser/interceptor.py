"""HTTP response interceptor for capturing API responses."""

from playwright.async_api import Page, Response
import asyncio
import logging
import re
from typing import Callable, Awaitable, Pattern

logger = logging.getLogger(__name__)


# Patterns de interes pentru interceptare

API_PATTERNS: dict[str, Pattern] = {
    "scheduled": re.compile(
        r"/api/v1/sport/([\w-]+)/scheduled-events/(\d{4}-\d{2}-\d{2})(?!/inverse)"
    ),
    "live": re.compile(r"/api/v1/sport/([\w-]+)/events/live"),
    "featured": re.compile(r"/api/v1/odds/\d+/featured-events/([\w-]+)"),
    "inverse": re.compile(
        r"/api/v1/sport/([\w-]+)/scheduled-events/(\d{4}-\d{2}-\d{2})/inverse"
    ),
}


class ResponseInterceptor:
    """
    Intercepts and processes HTTP responses from SofaScore API.

    Monitors network traffic for specific API patterns and routes
    responses to appropriate handlers.
    """

    def __init__(self):
        """Initialize response interceptor."""
        self.handlers: dict[str, list[Callable[[dict, re.Match], Awaitable[None]]]] = {
            pattern_name: [] for pattern_name in API_PATTERNS.keys()
        }
        self._queue: asyncio.Queue = asyncio.Queue()

    def on(
        self, pattern_name: str, handler: Callable[[dict, re.Match], Awaitable[None]]
    ) -> None:
        """
        Register a handler for a specific API pattern.

        Args:
            pattern_name: Name of the pattern (e.g., 'live', 'event', 'statistics')
            handler: Async function to handle the response data
                     Signature: async def handler(data: dict, match: re.Match) -> None

        Example:
            async def handle_live_matches(data: dict, match: re.Match) -> None:
                sport = match.group(1)
                print(f"Live matches for {sport}: {len(data['events'])}")

            interceptor.on('live', handle_live_matches)
        """
        if pattern_name not in API_PATTERNS:
            raise ValueError(
                f"Unknown pattern '{pattern_name}'. "
                f"Available: {list(API_PATTERNS.keys())}"
            )
        self.handlers[pattern_name].append(handler)
        logger.debug(f"Registered handler for pattern '{pattern_name}'")

    async def attach(self, page: Page) -> None:
        """
        Attach interceptor to a Playwright page.

        Args:
            page: Playwright page to monitor
        """
        page.on("response", self._on_response)
        logger.info("Response interceptor attached to page")

    async def _on_response(self, response: Response) -> None:
        """
        Internal handler for all responses.

        Args:
            response: Playwright Response object
        """
        url = response.url

        # Check if response matches any pattern
        for pattern_name, pattern in API_PATTERNS.items():
            match = pattern.search(url)
            if match:
                asyncio.create_task(
                    self._process_response(response, pattern_name, match)
                )
                break

    async def _process_response(
        self, response: Response, pattern_name: str, match: re.Match
    ) -> None:
        """
        Process a matched response.

        Args:
            response: Playwright Response object
            pattern_name: Name of matched pattern
            match: Regex match object
        """
        try:
            # Only process successful responses with JSON content
            if not response.ok:
                logger.debug(
                    f"Skipping non-OK response: {response.url} (status: {response.status})"
                )
                return

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                logger.debug(f"Skipping non-JSON response: {response.url}")
                return

            # Parse JSON response
            try:
                data = await response.json()
            except Exception as e:
                logger.warning(f"Failed to parse JSON from {response.url}: {e}")
                return

            # Log intercepted response
            logger.info(f"Intercepted {pattern_name}: {response.url}")

            # Call all registered handlers for this pattern
            handlers = self.handlers.get(pattern_name, [])
            if handlers:
                for handler in handlers:
                    try:
                        await handler(data, match)
                    except Exception as e:
                        logger.error(
                            f"Handler error for {pattern_name} ({response.url}): {e}",
                            exc_info=True,
                        )
            else:
                logger.debug(f"No handlers registered for pattern '{pattern_name}'")

        except Exception as e:
            logger.error(
                f"Error processing response {response.url}: {e}", exc_info=True
            )

    def remove_handler(self, pattern_name: str, handler: Callable) -> None:
        """
        Remove a specific handler for a pattern.

        Args:
            pattern_name: Name of the pattern
            handler: Handler function to remove
        """
        if pattern_name in self.handlers and handler in self.handlers[pattern_name]:
            self.handlers[pattern_name].remove(handler)
            logger.debug(f"Removed handler for pattern '{pattern_name}'")

    def clear_handlers(self, pattern_name: str | None = None) -> None:
        """
        Clear handlers for a specific pattern or all patterns.

        Args:
            pattern_name: Pattern name to clear, or None to clear all
        """
        if pattern_name:
            if pattern_name in self.handlers:
                self.handlers[pattern_name].clear()
                logger.debug(f"Cleared handlers for pattern '{pattern_name}'")
        else:
            for handlers_list in self.handlers.values():
                handlers_list.clear()
            logger.debug("Cleared all handlers")


async def create_interceptor(page: Page) -> ResponseInterceptor:
    """
    Create and attach a response interceptor to a page.

    Args:
        page: Playwright page to monitor

    Returns:
        ResponseInterceptor instance

    Example:
        interceptor = await create_interceptor(page)
        interceptor.on('live', my_handler)
        await page.goto('https://www.sofascore.com/football')
    """
    interceptor = ResponseInterceptor()
    await interceptor.attach(page)
    return interceptor
