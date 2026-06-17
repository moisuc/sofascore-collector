"""Capture SofaScore's dynamic API request headers (notably X-Requested-With).

SofaScore's frontend JS attaches a per-session token to its `/api/v1/...` XHR
calls via the `X-Requested-With` header (e.g. ``28a003``). The value is generated
client-side and cannot be computed, so we sniff it from the browser's own
requests and reuse it to fetch endpoint JSON directly.
"""

import logging
import re
from playwright.async_api import Page, Request

logger = logging.getLogger(__name__)

# Only sniff genuine API calls; the token is attached to these requests.
_API_REQUEST_PATTERN = re.compile(r"/api/v1/")

# Headers we must NOT replay verbatim - Playwright/the HTTP stack sets these and
# replaying stale values breaks the request. ``cookie`` is dropped because the
# replay goes through the context's APIRequestContext, which injects the live
# session cookies itself; a stale captured cookie would override them.
_STRIPPED_HEADERS = {
    "host",
    "content-length",
    "accept-encoding",
    "connection",
    "cookie",
}


class HeaderCapture:
    """Sniffs and stores the freshest API request headers from a page.

    Attaches a ``request`` listener to a Playwright page and keeps the
    ``X-Requested-With`` token captured on first access plus the full sanitized
    header set seen on a real ``/api/v1/`` request. These can then be replayed
    to fetch JSON directly via an ``APIRequestContext``.

    The full header set is read via ``request.all_headers()`` (not the
    synchronous ``request.headers`` snapshot) so the browser-added security
    headers (``sec-fetch-*``, ``sec-ch-ua*``, ...) are included - SofaScore's
    API returns 403 to replayed requests that lack them.
    """

    def __init__(self, page: Page | None = None):
        self.page = page
        self.token: str | None = None
        self.headers: dict[str, str] = {}

    @property
    def is_ready(self) -> bool:
        """True once a usable token has been captured."""
        return bool(self.token)

    async def attach(self, page: Page) -> None:
        """Attach the request listener to a page."""
        self.page = page
        page.on("request", self._on_request)
        logger.info("Header capture attached to page")

    async def _on_request(self, request: Request) -> None:
        """Capture token + full headers from matching API requests."""
        try:
            if not _API_REQUEST_PATTERN.search(request.url):
                return

            # all_headers() returns the complete lower-cased header set actually
            # sent on the wire, including the security headers the browser adds.
            headers = await request.all_headers()
            token = headers.get("x-requested-with")
            if not token:
                return

            sanitized = {
                k: v
                for k, v in headers.items()
                if not k.startswith(":") and k.lower() not in _STRIPPED_HEADERS
            }

            # Keep the token captured on first access; only log when it changes.
            if token != self.token:
                if self.token is None:
                    logger.info(f"Captured X-Requested-With token: {token}")
                else:
                    logger.info(f"X-Requested-With token refreshed: {token}")

            self.token = token
            self.headers = sanitized
        except Exception as e:
            logger.debug(f"Error capturing request headers: {e}")


async def create_header_capture(page: Page) -> HeaderCapture:
    """Create and attach a header capture to a page."""
    capture = HeaderCapture(page)
    await capture.attach(page)
    return capture
