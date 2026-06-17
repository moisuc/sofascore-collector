"""Intercept JSON traffic from 365scores' backend API (webws.365scores.com).

Unlike the SofaScore :class:`ResponseInterceptor`, this is a small dedicated
interceptor that only watches the 365scores ``webws`` host. It matches the
relevant endpoints by name (``allscores``/``current``) and hands the parsed JSON
plus capture context to registered handlers, which persist it raw.
"""

import asyncio
import logging
import re
from typing import Awaitable, Callable, Pattern
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Page, Response

logger = logging.getLogger(__name__)


# Endpoints of interest on webws.365scores.com. Keyed by a short name used for
# file naming and handler routing. Easy to extend (e.g. add ``game``).
SCORES365_PATTERNS: dict[str, Pattern] = {
    "allscores": re.compile(r"webws\.365scores\.com/web/games/allscores/"),
    "current": re.compile(r"webws\.365scores\.com/web/games/current/"),
}


# Handler receives (data, endpoint_name, url). ``data`` is the parsed JSON dict.
Scores365Handler = Callable[[dict, str, str], Awaitable[None]]


class Scores365Interceptor:
    """Capture JSON responses from 365scores' ``webws`` API.

    Attaches a ``response`` listener to a Playwright page and routes any
    response whose URL matches a known endpoint to the registered handlers.
    """

    page: Page | None

    def __init__(self, page: Page | None = None):
        self.page = page
        self.handlers: dict[str, list[Scores365Handler]] = {
            name: [] for name in SCORES365_PATTERNS
        }

    def on(self, endpoint: str, handler: Scores365Handler) -> None:
        """Register a handler for a specific endpoint (``allscores``/``current``)."""
        if endpoint not in SCORES365_PATTERNS:
            raise ValueError(
                f"Unknown endpoint '{endpoint}'. "
                f"Available: {list(SCORES365_PATTERNS.keys())}"
            )
        self.handlers[endpoint].append(handler)
        logger.debug(f"Registered 365scores handler for '{endpoint}'")

    async def attach(self, page: Page) -> None:
        """Attach the response listener to a page."""
        self.page = page
        page.on("response", self._on_response)
        logger.info("365scores interceptor attached to page")

    async def _on_response(self, response: Response) -> None:
        """Route matching responses to processing (sync-friendly, fire & forget)."""
        url = response.url
        for endpoint, pattern in SCORES365_PATTERNS.items():
            if pattern.search(url):
                asyncio.create_task(self._process_response(response, endpoint))
                break

    async def _process_response(self, response: Response, endpoint: str) -> None:
        """Parse JSON and dispatch to handlers for a matched response."""
        url = response.url
        try:
            if not response.ok:
                logger.debug(
                    f"Skipping non-OK 365scores response: {url} (status: {response.status})"
                )
                return

            try:
                data = await response.json()
            except Exception as e:
                logger.warning(f"Failed to parse 365scores JSON from {url}: {e}")
                return

            if not isinstance(data, dict):
                logger.warning(f"365scores response was not a JSON object: {url}")
                return

            logger.info(f"Intercepted 365scores {endpoint}: {url}")

            for handler in self.handlers.get(endpoint, []):
                try:
                    await handler(data, endpoint, url)
                except Exception as e:
                    logger.error(
                        f"365scores handler error for {endpoint} ({url}): {e}",
                        exc_info=True,
                    )
        except Exception as e:
            logger.error(f"Error processing 365scores response {url}: {e}", exc_info=True)

    def clear_handlers(self, endpoint: str | None = None) -> None:
        """Clear handlers for a specific endpoint or all of them."""
        if endpoint:
            self.handlers.get(endpoint, []).clear()
        else:
            for handlers in self.handlers.values():
                handlers.clear()


def extract_url_params(url: str) -> dict[str, str]:
    """Return a flat dict of the first value for each query param in ``url``."""
    query = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in query.items() if v}


async def create_scores365_interceptor(page: Page) -> Scores365Interceptor:
    """Create and attach a 365scores interceptor to a page."""
    interceptor = Scores365Interceptor(page)
    await interceptor.attach(page)
    return interceptor
