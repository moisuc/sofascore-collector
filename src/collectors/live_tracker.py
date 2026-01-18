"""Live match tracker that stays on the live page and monitors updates."""

import asyncio
import logging
import re
from typing import Any

from src.collectors.base import BaseCollector
from src.browser.manager import BrowserManager
from src.config import settings

logger = logging.getLogger(__name__)


class LiveTracker(BaseCollector):
    """
    Collector that stays on the live scores page and tracks real-time updates.

    This collector:
    - Navigates to the live page for a specific sport
    - Monitors HTTP API responses for live match data
    - Monitors WebSocket messages for real-time score updates
    - Refreshes the page periodically to maintain connection
    - Processes live events, scores, incidents, and statistics
    """

    # Base URL patterns for each sport's live page
    LIVE_URLS = {
        "football": "https://www.sofascore.com/football",
        "tennis": "https://www.sofascore.com/tennis",
        "basketball": "https://www.sofascore.com/basketball",
        "handball": "https://www.sofascore.com/handball",
        "volleyball": "https://www.sofascore.com/volleyball",
        "ice-hockey": "https://www.sofascore.com/ice-hockey",
    }

    def __init__(
        self,
        browser_manager: BrowserManager,
        sport: str,
        on_live_data: Any = None,
        on_scheduled_data: Any = None,
        on_featured_data: Any = None,
        on_inverse_data: Any = None,
        on_score_update: Any = None,
        on_incident: Any = None,
    ):
        """
        Initialize live tracker.

        Args:
            browser_manager: BrowserManager instance
            sport: Sport to track (e.g., 'football', 'tennis')
            on_live_data: Async callback for live match data from HTTP responses
                          Signature: async def(data: dict, match: re.Match) -> None
            on_scheduled_data: Async callback for scheduled match data from HTTP responses
                              Signature: async def(data: dict, match: re.Match) -> None
            on_featured_data: Async callback for featured match data from HTTP responses
                             Signature: async def(data: dict, match: re.Match) -> None
            on_inverse_data: Async callback for inverse scheduled match data from HTTP responses
                            Signature: async def(data: dict, match: re.Match) -> None
            on_score_update: Async callback for WebSocket score updates
                           Signature: async def(data: dict) -> None
            on_incident: Async callback for WebSocket incident updates
                        Signature: async def(data: dict) -> None

        Raises:
            ValueError: If sport is not supported
        """
        if sport not in self.LIVE_URLS:
            raise ValueError(
                f"Unsupported sport '{sport}'. Supported: {list(self.LIVE_URLS.keys())}"
            )

        super().__init__(browser_manager, sport=sport, context_name=f"live_{sport}")

        self.url = self.LIVE_URLS[sport]
        self.on_live_data = on_live_data
        self.on_scheduled_data = on_scheduled_data
        self.on_featured_data = on_featured_data
        self.on_inverse_data = on_inverse_data
        self.on_score_update = on_score_update
        self.on_incident = on_incident

        self._refresh_task: asyncio.Task | None = None

    async def setup(self) -> None:
        """Setup page and register interceptor handlers."""
        await super().setup()

        # Register HTTP response handlers
        if self.http_interceptor:
            if self.on_live_data:
                self.http_interceptor.on("live", self._handle_live_response)
                logger.debug(f"Registered HTTP handler for live {self.sport} data")

            if self.on_scheduled_data:
                self.http_interceptor.on("scheduled", self._handle_scheduled_response)
                logger.debug(f"Registered HTTP handler for scheduled {self.sport} data")

            if self.on_featured_data:
                self.http_interceptor.on("featured", self._handle_featured_response)
                logger.debug(f"Registered HTTP handler for featured {self.sport} data")

            if self.on_inverse_data:
                
                self.http_interceptor.on("inverse", self._handle_inverse_response)
                logger.debug(f"Registered HTTP handler for inverse {self.sport} data")

        # Register WebSocket handlers
        if self.ws_interceptor:
            # Use LiveScoreWebSocketInterceptor if we have score/incident handlers
            if hasattr(self.ws_interceptor, "on_score_update"):
                if self.on_score_update:
                    self.ws_interceptor.on_score_update(self.on_score_update)  # type: ignore[misc]
                    logger.debug(f"Registered score update handler for {self.sport}")

                if self.on_incident:
                    self.ws_interceptor.on_incident(self.on_incident)  # type: ignore[misc]
                    logger.debug(f"Registered incident handler for {self.sport}")
            else:
                # Fallback to generic message handler
                if self.on_score_update or self.on_incident:
                    self.ws_interceptor.on_message(self._handle_ws_message)
                    logger.debug(f"Registered generic WS handler for {self.sport}")

    async def collect(self) -> None:
        """
        Main collection logic for live tracking.

        This method:
        1. Navigates to the live page
        2. Handles cookie consent dialog if it appears
        3. Clicks "Show all" buttons to expand content
        4. Waits for initial data load
        5. Sets up periodic page refresh
        6. Keeps running until stopped
        """
        logger.info(f"Starting live tracker for {self.sport}")

        # Navigate to live page
        await self.navigate_with_delay(self.url, wait_until="networkidle")

        # Handle consent dialog if it appears
        await self.handle_consent_dialog(timeout=5.0)

        # Click "Show all" buttons if enabled
        if settings.click_show_all:
            await self.click_show_all_buttons(wait_after=settings.show_all_wait_after)

        # Wait for initial data to be intercepted
        await self.wait_for_data(timeout=5.0)
        logger.info(f"Initial data loaded for {self.sport}")

        # Start periodic refresh to maintain connection
        self._refresh_task = asyncio.create_task(self._periodic_refresh())

        # Keep running and processing events
        try:
            while self._running:
                # Just keep the event loop running
                # All data processing happens in interceptor callbacks
                await asyncio.sleep(60)
                logger.debug(
                    f"Live tracker for {self.sport} still active "
                    f"(WS connections: {self.ws_interceptor.active_connections if self.ws_interceptor else 0})"
                )
        except asyncio.CancelledError:
            logger.info(f"Live tracker for {self.sport} cancelled")
            raise
        finally:
            if self._refresh_task:
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass

    async def _periodic_refresh(self) -> None:
        """Refresh the page periodically to maintain connection."""
        interval = settings.page_refresh_interval
        logger.info(
            f"Starting periodic refresh for {self.sport} (interval: {interval}s)"
        )

        while self._running:
            try:
                await asyncio.sleep(interval)

                if not self.page or self.page.is_closed():
                    logger.warning(
                        f"Page closed for {self.sport}, stopping refresh task"
                    )
                    break

                logger.info(f"Refreshing live page for {self.sport}")
                await self.page.reload(wait_until="networkidle", timeout=60000)
                if settings.click_show_all:
                    await self.click_show_all_buttons(wait_after=settings.show_all_wait_after)
                logger.debug(f"Page refreshed successfully for {self.sport}")

            except asyncio.CancelledError:
                logger.debug(f"Refresh task cancelled for {self.sport}")
                raise
            except Exception as e:
                logger.error(f"Error refreshing page for {self.sport}: {e}")
                # Continue trying despite errors

    async def _handle_live_response(self, data: dict, match: re.Match) -> None:
        """
        Handle intercepted live events HTTP response.

        Args:
            data: JSON response data
            match: Regex match object containing URL groups
        """
        try:
            sport_from_url = match.group(1) if match.lastindex and match.lastindex >= 1 else None

            # Verify this is our sport
            if sport_from_url and sport_from_url != self.sport:
                logger.debug(
                    f"Ignoring live data for different sport: {sport_from_url}"
                )
                return

            logger.info(
                f"Live data intercepted for {self.sport}: "
                f"{len(data.get('events', []))} events"
            )

            # Call user-provided handler
            if self.on_live_data:
                await self.on_live_data(data, match)

        except Exception as e:
            logger.error(
                f"Error handling live response for {self.sport}: {e}", exc_info=True
            )

    async def _handle_scheduled_response(self, data: dict, match: re.Match) -> None:
        """
        Handle intercepted scheduled events HTTP response.

        Args:
            data: JSON response data
            match: Regex match object containing URL groups
        """
        try:
            sport_from_url = match.group(1) if match.lastindex and match.lastindex >= 1 else None

            # Verify this is our sport
            if sport_from_url and sport_from_url != self.sport:
                logger.debug(
                    f"Ignoring scheduled data for different sport: {sport_from_url}"
                )
                return

            logger.info(
                f"Scheduled data intercepted for {self.sport}: "
                f"{len(data.get('events', []))} events"
            )

            # Call user-provided handler
            if self.on_scheduled_data:
                await self.on_scheduled_data(data, match)

        except Exception as e:
            logger.error(
                f"Error handling scheduled response for {self.sport}: {e}", exc_info=True
            )

    async def _handle_featured_response(self, data: dict, match: re.Match) -> None:
        """
        Handle intercepted featured events HTTP response.

        Args:
            data: JSON response data
            match: Regex match object containing URL groups
        """
        try:
            sport_from_url = match.group(1) if match.lastindex and match.lastindex >= 1 else None

            # Verify this is our sport
            if sport_from_url and sport_from_url != self.sport:
                logger.debug(
                    f"Ignoring featured data for different sport: {sport_from_url}"
                )
                return

            logger.info(
                f"Featured data intercepted for {self.sport}: "
                f"{len(data.get('events', []))} events"
            )

            # Call user-provided handler
            if self.on_featured_data:
                await self.on_featured_data(data, match)

        except Exception as e:
            logger.error(
                f"Error handling featured response for {self.sport}: {e}", exc_info=True
            )

    async def _handle_inverse_response(self, data: dict, match: re.Match) -> None:
        """
        Handle intercepted inverse scheduled events HTTP response.

        Args:
            data: JSON response data
            match: Regex match object containing URL groups
        """
        try:
            sport_from_url = match.group(1) if match.lastindex and match.lastindex >= 1 else None

            # Verify this is our sport
            if sport_from_url and sport_from_url != self.sport:
                logger.debug(
                    f"Ignoring inverse data for different sport: {sport_from_url}"
                )
                return

            logger.info(
                f"Inverse data intercepted for {self.sport}: "
                f"{len(data.get('events', []))} events"
            )

            # Call user-provided handler
            if self.on_inverse_data:
                await self.on_inverse_data(data, match)

        except Exception as e:
            logger.error(
                f"Error handling inverse response for {self.sport}: {e}", exc_info=True
            )

    async def _handle_ws_message(self, data: dict) -> None:
        """
        Handle WebSocket message (fallback for generic interceptor).

        Args:
            data: Parsed WebSocket message
        """
        try:
            message_type = data.get("type", "")

            # Route to appropriate handler based on type
            if message_type in ("score", "scoreChange", "scoreUpdate"):
                if self.on_score_update:
                    await self.on_score_update(data)
            elif message_type in ("incident", "incidentChange", "newIncident"):
                if self.on_incident:
                    await self.on_incident(data)
            else:
                logger.debug(
                    f"Unhandled WS message type for {self.sport}: {message_type}"
                )

        except Exception as e:
            logger.error(
                f"Error handling WS message for {self.sport}: {e}", exc_info=True
            )

    async def cleanup(self) -> None:
        """Cleanup resources including refresh task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        await super().cleanup()


async def create_live_tracker(
    browser_manager: BrowserManager,
    sport: str,
    on_live_data: Any = None,
    on_scheduled_data: Any = None,
    on_featured_data: Any = None,
    on_inverse_data: Any = None,
    on_score_update: Any = None,
    on_incident: Any = None,
) -> LiveTracker:
    """
    Create and start a live tracker for a sport.

    Args:
        browser_manager: BrowserManager instance
        sport: Sport to track
        on_live_data: Callback for live match data
        on_scheduled_data: Callback for scheduled match data
        on_featured_data: Callback for featured match data
        on_inverse_data: Callback for inverse scheduled match data
        on_score_update: Callback for score updates
        on_incident: Callback for incidents

    Returns:
        LiveTracker instance (already started)

    Example:
        async def handle_live_matches(data: dict, match: re.Match) -> None:
            events = data.get('events', [])
            print(f"Live matches: {len(events)}")

        tracker = await create_live_tracker(
            browser_manager,
            sport='football',
            on_live_data=handle_live_matches
        )
    """
    tracker = LiveTracker(
        browser_manager,
        sport=sport,
        on_live_data=on_live_data,
        on_scheduled_data=on_scheduled_data,
        on_featured_data=on_featured_data,
        on_inverse_data=on_inverse_data,
        on_score_update=on_score_update,
        on_incident=on_incident,
    )
    await tracker.start()
    return tracker
