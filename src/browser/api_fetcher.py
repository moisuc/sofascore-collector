"""Direct SofaScore API fetcher using the captured X-Requested-With token.

SofaScore's ``/api/v1/...`` endpoints return 403 unless the request carries the
per-session ``X-Requested-With`` token *and* originates from the real browser.
Replaying the token through Playwright's ``APIRequestContext`` still gets a 403
(different TLS/HTTP fingerprint), so we instead run a ``fetch()`` inside the live
page via ``page.evaluate``: same browser, same cookies, same fingerprint, with
the captured token attached explicitly. This lets us pull endpoint JSON without
navigating a full page.
"""

import logging
import re

from playwright.async_api import Page

from src.browser.header_capture import HeaderCapture
from src.browser.interceptor import API_PATTERNS

logger = logging.getLogger(__name__)

API_BASE = "https://www.sofascore.com/api/v1"


class DirectApiFetcher:
    """Fetch SofaScore API JSON directly via an in-page ``fetch()``.

    Builds canonical API URLs for the deterministic patterns
    (``scheduled``/``live``/``inverse``) and replays a previously seen URL for
    ``featured`` (whose path contains a non-derivable odds-provider id). Returns
    ``None`` on any failure so callers can fall back to page navigation.
    """

    def __init__(self, page: Page, header_capture: HeaderCapture):
        self.page = page
        self.header_capture = header_capture

    def build_url(self, pattern: str, sport: str | None = None, date: str | None = None) -> str | None:
        """Construct an API URL for a deterministic pattern.

        Args:
            pattern: One of ``scheduled``, ``live``, ``inverse``.
            sport: Sport slug (required for all deterministic patterns).
            date: Date string ``YYYY-MM-DD`` (required for scheduled/inverse).

        Returns:
            Fully-qualified URL, or ``None`` if it cannot be built.
        """
        if pattern == "live" and sport:
            return f"{API_BASE}/sport/{sport}/events/live"
        if pattern == "scheduled" and sport and date:
            return f"{API_BASE}/sport/{sport}/scheduled-events/{date}"
        if pattern == "inverse" and sport and date:
            return f"{API_BASE}/sport/{sport}/scheduled-events/{date}/inverse"
        return None

    async def fetch(
        self,
        pattern: str,
        sport: str | None = None,
        date: str | None = None,
        url: str | None = None,
    ) -> tuple[dict, re.Match] | None:
        """Fetch and parse API JSON for a pattern.

        Either provide ``url`` directly (e.g. a captured ``featured`` URL) or
        the parameters needed to build it.

        Returns:
            ``(data, match)`` where ``match`` is produced by re-running the
            pattern regex against the URL (so existing handlers work unchanged),
            or ``None`` on failure.
        """
        if not self.header_capture.is_ready:
            logger.debug("Direct fetch skipped: no token captured yet")
            return None

        target_url = url or self.build_url(pattern, sport=sport, date=date)
        if not target_url:
            logger.debug(f"Direct fetch skipped: could not build URL for '{pattern}'")
            return None

        regex = API_PATTERNS.get(pattern)
        if not regex:
            logger.debug(f"Direct fetch skipped: unknown pattern '{pattern}'")
            return None

        match = regex.search(target_url)
        if not match:
            logger.debug(f"Direct fetch skipped: URL did not match '{pattern}': {target_url}")
            return None

        if not self.page or self.page.is_closed():
            logger.debug("Direct fetch skipped: page not available")
            return None

        # Run the fetch INSIDE the page so it uses the real browser fingerprint
        # and session cookies. The X-Requested-With token captured on first
        # access is attached explicitly - it is what SofaScore validates, and
        # the browser does not add it to manual fetch() calls.
        token = self.header_capture.token
        try:
            result = await self.page.evaluate(
                """async ({ url, token }) => {
                    // Default ('same-origin') credentials: the API lives on a
                    // different origin than the localized page (sofascore.com vs
                    // sofascore.ro), and a credentialed cross-origin request is
                    // blocked by CORS. The token alone is enough for a 200.
                    const resp = await fetch(url, {
                        headers: { 'x-requested-with': token },
                    });
                    const body = resp.ok ? await resp.json() : null;
                    return { status: resp.status, body };
                }""",
                {"url": target_url, "token": token},
            )
        except Exception as e:
            logger.warning(f"Direct fetch error for {target_url}: {e}; falling back")
            return None

        status = result.get("status")
        if status != 200:
            logger.warning(
                f"Direct fetch failed for {target_url} (status: {status}); falling back"
            )
            return None

        data = result.get("body")
        if not isinstance(data, dict):
            logger.warning(f"Direct fetch returned non-object JSON for {target_url}")
            return None

        logger.info(f"Direct fetch ok ({pattern}): {target_url}")
        return data, match
