"""Daily events collector that navigates through dates to collect scheduled matches."""

import asyncio
import logging
import re
from datetime import date, timedelta
from typing import Any

from src.collectors.base import BaseCollector
from src.browser.manager import BrowserManager
from src.config import settings

logger = logging.getLogger(__name__)


class DailyEventsCollector(BaseCollector):
    """
    Collector that navigates through daily schedule pages to collect match data.

    This collector:
    - Navigates to scheduled events pages for specific dates
    - Intercepts API responses for scheduled matches
    - Can collect historical data (backfill) or upcoming matches
    - Processes match details, lineups, and statistics for scheduled events
    """

    # URL pattern for scheduled events: /football/2024-12-30
    SCHEDULED_URL_TEMPLATE = "https://www.sofascore.com/{sport}/{date}"

    def __init__(
        self,
        browser_manager: BrowserManager,
        sport: str,
        start_date: date | None = None,
        end_date: date | None = None,
        on_scheduled_data: Any = None,
        backfill_mode: bool = False,
    ):
        """
        Initialize daily events collector.

        Args:
            browser_manager: BrowserManager instance
            sport: Sport to collect (e.g., 'football', 'tennis')
            start_date: Start date for collection (defaults to today)
            end_date: End date for collection (defaults to start_date)
            on_scheduled_data: Async callback for scheduled match data
                              Signature: async def(data: dict, match: re.Match) -> None
            backfill_mode: If True, uses backfill delay between requests

        Example:
            # Collect next 7 days
            collector = DailyEventsCollector(
                browser_manager,
                sport='football',
                start_date=date.today(),
                end_date=date.today() + timedelta(days=7),
                on_scheduled_data=handle_matches
            )
        """
        super().__init__(browser_manager, sport=sport, context_name=f"daily_{sport}")

        self.start_date = start_date or date.today()
        self.end_date = end_date or self.start_date
        self.on_scheduled_data = on_scheduled_data
        self.backfill_mode = backfill_mode

        # Validate date range
        if self.end_date < self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) cannot be before start_date ({self.start_date})"
            )

        # Calculate total days to process
        self.total_days = (self.end_date - self.start_date).days + 1
        self.processed_days = 0
        self._consent_handled = False  # Track if consent dialog was handled

        logger.info(
            f"DailyEventsCollector initialized for {sport}: "
            f"{self.start_date} to {self.end_date} ({self.total_days} days)"
        )

    async def setup(self) -> None:
        """Setup page and register interceptor handlers."""
        await super().setup()

        # Register HTTP response handler for scheduled events
        if self.http_interceptor and self.on_scheduled_data:
            self.http_interceptor.on("scheduled", self._handle_scheduled_response)
            logger.debug(f"Registered HTTP handler for scheduled {self.sport} data")

    async def collect(self) -> None:
        """
        Main collection logic for daily events.

        Iterates through dates and collects scheduled matches for each day.
        """
        logger.info(
            f"Starting daily events collection for {self.sport} "
            f"({self.start_date} to {self.end_date})"
        )

        current_date = self.start_date

        while current_date <= self.end_date and self._running:
            try:
                await self._collect_date(current_date)
                self.processed_days += 1

                logger.info(
                    f"Progress: {self.processed_days}/{self.total_days} days processed "
                    f"for {self.sport}"
                )

                # Move to next date
                current_date += timedelta(days=1)

                # Apply backfill delay if in backfill mode
                if self.backfill_mode and current_date <= self.end_date:
                    delay = settings.backfill_delay
                    logger.debug(f"Backfill delay: {delay}s before next date")
                    await asyncio.sleep(delay)

            except asyncio.CancelledError:
                logger.info(f"Daily events collection cancelled for {self.sport}")
                raise
            except Exception as e:
                logger.error(
                    f"Error collecting data for {current_date} ({self.sport}): {e}",
                    exc_info=True,
                )
                # Continue with next date despite errors
                current_date += timedelta(days=1)

        logger.info(
            f"Daily events collection complete for {self.sport}: "
            f"{self.processed_days}/{self.total_days} days processed"
        )

        # Stop the collector after completing the date range
        self._running = False

    async def _collect_date(self, target_date: date) -> None:
        """
        Collect scheduled events for a specific date.

        Args:
            target_date: Date to collect events for
        """
        date_str = target_date.strftime("%Y-%m-%d")
        url = self.SCHEDULED_URL_TEMPLATE.format(sport=self.sport, date=date_str)

        logger.info(f"Collecting scheduled events for {self.sport} on {date_str}")

        # Navigate to date page
        # Use 'domcontentloaded' instead of 'networkidle' because WebSocket connections
        # and periodic API calls prevent networkidle from ever being reached, causing timeouts.
        # The HTTP interceptor captures the scheduled events API response regardless of wait strategy.
        await self.navigate_with_delay(url, wait_until="domcontentloaded")

        # Handle consent dialog on first navigation only
        if not self._consent_handled:
            self._consent_handled = await self.handle_consent_dialog(timeout=5.0)

        # Click "Show all" buttons to expand all collapsed match lists
        buttons_clicked = await self.click_show_all_buttons(wait_after=2.0)
        if buttons_clicked > 0:
            logger.info(f"Expanded {buttons_clicked} collapsed section(s) on {date_str}")

        # Wait for API responses to be intercepted
        await self.wait_for_data(timeout=5.0)

        logger.debug(f"Data collection complete for {date_str}")

    async def _handle_scheduled_response(self, data: dict, match: re.Match) -> None:
        """
        Handle intercepted scheduled events HTTP response.

        Args:
            data: JSON response data
            match: Regex match object containing URL groups
                   Group 1: sport
                   Group 2: date (YYYY-MM-DD)
        """
        try:
            # Extract sport and date from URL
            sport_from_url = match.group(1) if match.lastindex and match.lastindex >= 1 else None
            date_from_url = match.group(2) if match.lastindex and match.lastindex >= 2 else None

            # Verify this is our sport
            if sport_from_url and sport_from_url != self.sport:
                logger.debug(
                    f"Ignoring scheduled data for different sport: {sport_from_url}"
                )
                return

            logger.info(
                f"Scheduled data intercepted for {self.sport} on {date_from_url}: "
                f"{len(data.get('events', []))} events"
            )

            # Call user-provided handler
            if self.on_scheduled_data:
                await self.on_scheduled_data(data, match)

        except Exception as e:
            logger.error(
                f"Error handling scheduled response for {self.sport}: {e}",
                exc_info=True,
            )

    def get_progress(self) -> dict[str, Any]:
        """
        Get collection progress information.

        Returns:
            Dictionary with progress details
        """
        return {
            "sport": self.sport,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_days": self.total_days,
            "processed_days": self.processed_days,
            "progress_percent": (self.processed_days / self.total_days * 100)
            if self.total_days > 0
            else 0,
            "is_running": self._running,
        }


async def create_daily_collector(
    browser_manager: BrowserManager,
    sport: str,
    start_date: date | None = None,
    end_date: date | None = None,
    on_scheduled_data: Any = None,
    backfill_mode: bool = False,
    auto_start: bool = True,
) -> DailyEventsCollector:
    """
    Create a daily events collector.

    Args:
        browser_manager: BrowserManager instance
        sport: Sport to collect
        start_date: Start date (defaults to today)
        end_date: End date (defaults to start_date)
        on_scheduled_data: Callback for scheduled match data
        backfill_mode: Enable backfill delay between requests
        auto_start: Automatically start the collector

    Returns:
        DailyEventsCollector instance

    Example:
        # Collect upcoming week
        async def handle_scheduled(data: dict, match: re.Match) -> None:
            events = data.get('events', [])
            print(f"Scheduled matches: {len(events)}")

        collector = await create_daily_collector(
            browser_manager,
            sport='football',
            end_date=date.today() + timedelta(days=7),
            on_scheduled_data=handle_scheduled
        )

        # Wait for completion
        while collector.is_running():
            await asyncio.sleep(1)
    """
    collector = DailyEventsCollector(
        browser_manager,
        sport=sport,
        start_date=start_date,
        end_date=end_date,
        on_scheduled_data=on_scheduled_data,
        backfill_mode=backfill_mode,
    )

    if auto_start:
        await collector.start()

    return collector


async def backfill_historical_data(
    browser_manager: BrowserManager,
    sport: str,
    days_back: int = 30,
    on_scheduled_data: Any = None,
) -> DailyEventsCollector:
    """
    Convenience function to backfill historical data.

    Args:
        browser_manager: BrowserManager instance
        sport: Sport to backfill
        days_back: Number of days to go back from today
        on_scheduled_data: Callback for scheduled match data

    Returns:
        DailyEventsCollector instance (already started)

    Example:
        # Backfill last 30 days of football matches
        collector = await backfill_historical_data(
            browser_manager,
            sport='football',
            days_back=30,
            on_scheduled_data=save_to_db
        )
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    logger.info(
        f"Starting historical backfill for {sport}: "
        f"{start_date} to {end_date} ({days_back} days)"
    )

    return await create_daily_collector(
        browser_manager,
        sport=sport,
        start_date=start_date,
        end_date=end_date,
        on_scheduled_data=on_scheduled_data,
        backfill_mode=True,
        auto_start=True,
    )
