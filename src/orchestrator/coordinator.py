"""Multi-collector orchestrator for coordinating data collection across sports."""

import asyncio
import logging
import signal
from typing import Any
from datetime import date, timedelta

from src.browser.manager import BrowserManager
from src.collectors import LiveTracker, DailyEventsCollector
from src.config import settings
from src.orchestrator.handlers import DataHandler
from src.storage.database import init_db

logger = logging.getLogger(__name__)


class CollectorCoordinator:
    """
    Coordinates multiple data collectors across different sports.

    Manages:
    - Browser manager lifecycle
    - Multiple live trackers and daily collectors
    - Database persistence via handlers
    - Graceful shutdown
    """

    def __init__(self, headless: bool | None = None):
        """
        Initialize coordinator.

        Args:
            headless: Run browsers in headless mode (defaults to settings.headless)
        """
        self.headless = headless if headless is not None else settings.headless
        self.browser_manager: BrowserManager | None = None
        self.collectors: dict[str, LiveTracker | DailyEventsCollector] = {}
        self.handler: DataHandler | None = None
        self._running = False
        self._shutdown_event = asyncio.Event()

        logger.info("CollectorCoordinator initialized")

    async def initialize(self) -> None:
        """
        Initialize coordinator resources.

        Sets up:
        - Database
        - Browser manager
        - Data handler
        """
        logger.info("Initializing coordinator resources...")

        # Initialize database
        init_db()
        logger.info("Database initialized")

        # Create browser manager
        self.browser_manager = BrowserManager(headless=self.headless)
        await self.browser_manager.__aenter__()
        logger.info(f"Browser manager started (headless={self.headless})")

        # Create data handler (creates session per operation for SQLite safety)
        self.handler = DataHandler()
        logger.info("Data handler initialized")

        self._running = True
        logger.info("Coordinator initialization complete")

    async def add_live_tracker(
        self,
        sport: str,
        auto_start: bool = True
    ) -> LiveTracker:
        """
        Add a live tracker for a sport.

        Args:
            sport: Sport to track (e.g., 'football', 'tennis')
            auto_start: Automatically start the tracker

        Returns:
            LiveTracker instance

        Raises:
            RuntimeError: If coordinator not initialized
        """
        if not self.browser_manager or not self.handler:
            raise RuntimeError("Coordinator not initialized. Call initialize() first.")

        collector_id = f"live_{sport}"

        if collector_id in self.collectors:
            logger.warning(f"Live tracker for {sport} already exists")
            return self.collectors[collector_id]

        logger.info(f"Adding live tracker for {sport}")

        # Create tracker with handlers
        tracker = LiveTracker(
            browser_manager=self.browser_manager,
            sport=sport,
            on_live_data=self.handler.handle_live_events,
            on_scheduled_data=self.handler.handle_scheduled_events,
            on_score_update=self.handler.handle_score_update,
            on_incident=self.handler.handle_incident,
        )

        self.collectors[collector_id] = tracker

        if auto_start:
            await tracker.start()
            logger.info(f"Live tracker for {sport} started")

        return tracker

    async def add_daily_collector(
        self,
        sport: str,
        start_date: date | None = None,
        end_date: date | None = None,
        backfill_mode: bool = False,
        auto_start: bool = True,
    ) -> DailyEventsCollector:
        """
        Add a daily events collector for a sport.

        Args:
            sport: Sport to collect
            start_date: Start date (defaults to today)
            end_date: End date (defaults to start_date)
            backfill_mode: Enable backfill delay between requests
            auto_start: Automatically start the collector

        Returns:
            DailyEventsCollector instance

        Raises:
            RuntimeError: If coordinator not initialized
        """
        if not self.browser_manager or not self.handler:
            raise RuntimeError("Coordinator not initialized. Call initialize() first.")

        # Generate unique collector ID
        start = start_date or date.today()
        end = end_date or start
        collector_id = f"daily_{sport}_{start.isoformat()}_{end.isoformat()}"

        if collector_id in self.collectors:
            logger.warning(f"Daily collector for {sport} ({start} to {end}) already exists")
            return self.collectors[collector_id]

        logger.info(f"Adding daily collector for {sport} ({start} to {end})")

        # Create collector with handler
        collector = DailyEventsCollector(
            browser_manager=self.browser_manager,
            sport=sport,
            start_date=start,
            end_date=end,
            on_scheduled_data=self.handler.handle_scheduled_events,
            backfill_mode=backfill_mode,
        )

        self.collectors[collector_id] = collector

        if auto_start:
            await collector.start()
            logger.info(f"Daily collector for {sport} started")

        return collector

    async def add_live_trackers_for_all_sports(self) -> list[LiveTracker]:
        """
        Add live trackers for all configured sports.

        Uses sports list from settings.

        Returns:
            List of LiveTracker instances
        """
        trackers = []

        for sport in settings.sports:
            try:
                tracker = await self.add_live_tracker(sport, auto_start=True)
                trackers.append(tracker)
            except Exception as e:
                logger.error(f"Failed to add live tracker for {sport}: {e}", exc_info=True)
                # Continue with other sports

        logger.info(f"Added {len(trackers)}/{len(settings.sports)} live trackers")
        return trackers

    async def backfill_historical_data(
        self,
        sport: str,
        days_back: int = 30,
    ) -> DailyEventsCollector:
        """
        Backfill historical data for a sport.

        Args:
            sport: Sport to backfill
            days_back: Number of days to go back from today

        Returns:
            DailyEventsCollector instance
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        logger.info(f"Starting historical backfill for {sport}: {days_back} days")

        return await self.add_daily_collector(
            sport=sport,
            start_date=start_date,
            end_date=end_date,
            backfill_mode=True,
            auto_start=True,
        )

    async def collect_upcoming_matches(
        self,
        sport: str,
        days_ahead: int = 7,
    ) -> DailyEventsCollector:
        """
        Collect upcoming matches for a sport.

        Args:
            sport: Sport to collect
            days_ahead: Number of days ahead to collect

        Returns:
            DailyEventsCollector instance
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=days_ahead)

        logger.info(f"Collecting upcoming matches for {sport}: {days_ahead} days ahead")

        return await self.add_daily_collector(
            sport=sport,
            start_date=start_date,
            end_date=end_date,
            backfill_mode=False,
            auto_start=True,
        )

    async def collect_schedule_window(
        self,
        sport: str,
        days_past: int = 3,
        days_future: int = 3,
    ) -> DailyEventsCollector:
        """
        Collect matches in a time window around today (past + future).

        This is a convenience method that combines historical backfill and
        upcoming match collection into a single date range collection.

        Args:
            sport: Sport to collect
            days_past: Number of days to go back from today (default: 3)
            days_future: Number of days ahead from today (default: 3)

        Returns:
            DailyEventsCollector instance

        Example:
            # Collect past 3 days + today + future 3 days (7 days total)
            collector = await coordinator.collect_schedule_window(
                sport='football',
                days_past=3,
                days_future=3
            )
        """
        start_date = date.today() - timedelta(days=days_past)
        end_date = date.today() + timedelta(days=days_future)
        total_days = days_past + 1 + days_future

        logger.info(
            f"Collecting schedule window for {sport}: "
            f"{days_past} days past + today + {days_future} days future "
            f"({total_days} days total, {start_date} to {end_date})"
        )

        return await self.add_daily_collector(
            sport=sport,
            start_date=start_date,
            end_date=end_date,
            backfill_mode=True,  # Use backfill delay since we're collecting historical data
            auto_start=True,
        )

    async def collect_schedule_window_for_all_sports(
        self,
        days_past: int = 3,
        days_future: int = 3,
    ) -> list[DailyEventsCollector]:
        """
        Collect schedule window for all configured sports.

        Runs collect_schedule_window() sequentially for each sport in settings.sports
        to avoid overwhelming the browser manager with too many concurrent contexts.

        Args:
            days_past: Number of days to go back from today (default: 3)
            days_future: Number of days ahead from today (default: 3)

        Returns:
            List of DailyEventsCollector instances

        Example:
            # Collect 7-day window for all sports
            collectors = await coordinator.collect_schedule_window_for_all_sports(
                days_past=3,
                days_future=3
            )

            # Wait for all to complete
            for collector in collectors:
                while collector.is_running():
                    await asyncio.sleep(5)
        """
        collectors = []

        logger.info(
            f"Starting schedule window collection for {len(settings.sports)} sports: "
            f"{days_past} days past + {days_future} days future"
        )

        for sport in settings.sports:
            try:
                collector = await self.collect_schedule_window(
                    sport=sport,
                    days_past=days_past,
                    days_future=days_future,
                )
                collectors.append(collector)

                logger.info(f"Started schedule window collection for {sport}")

                # Wait for this sport to complete before starting the next one
                # This prevents browser context overload
                while collector.is_running():
                    await asyncio.sleep(2)

                logger.info(f"Completed schedule window collection for {sport}")

            except Exception as e:
                logger.error(
                    f"Failed to collect schedule window for {sport}: {e}",
                    exc_info=True
                )
                # Continue with other sports

        logger.info(
            f"Schedule window collection complete: "
            f"{len(collectors)}/{len(settings.sports)} sports processed"
        )

        return collectors

    async def stop_collector(self, collector_id: str) -> None:
        """
        Stop a specific collector.

        Args:
            collector_id: Collector identifier (e.g., 'live_football')
        """
        if collector_id not in self.collectors:
            logger.warning(f"Collector '{collector_id}' not found")
            return

        collector = self.collectors[collector_id]
        logger.info(f"Stopping collector: {collector_id}")

        try:
            await collector.stop()
            logger.info(f"Collector '{collector_id}' stopped")
        except Exception as e:
            logger.error(f"Error stopping collector '{collector_id}': {e}", exc_info=True)

    async def stop_all_collectors(self) -> None:
        """Stop all running collectors."""
        logger.info(f"Stopping all collectors ({len(self.collectors)} total)...")

        # Stop all collectors concurrently
        tasks = []
        for collector_id, collector in self.collectors.items():
            if collector.is_running():
                tasks.append(collector.stop())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error stopping collector: {result}")

        logger.info("All collectors stopped")

    async def cleanup(self) -> None:
        """Cleanup all resources."""
        logger.info("Cleaning up coordinator resources...")

        # Stop all collectors
        await self.stop_all_collectors()

        # Close browser manager
        if self.browser_manager:
            try:
                await self.browser_manager.__aexit__(None, None, None)
                logger.info("Browser manager closed")
            except Exception as e:
                logger.error(f"Error closing browser manager: {e}", exc_info=True)

        self._running = False
        logger.info("Coordinator cleanup complete")

    def get_status(self) -> dict[str, Any]:
        """
        Get coordinator status.

        Returns:
            Dictionary with status information
        """
        collector_statuses = {}

        for collector_id, collector in self.collectors.items():
            status = {
                "running": collector.is_running(),
                "type": "live" if isinstance(collector, LiveTracker) else "daily",
                "sport": collector.sport,
            }

            # Add progress info for daily collectors
            if isinstance(collector, DailyEventsCollector):
                status["progress"] = collector.get_progress()

            collector_statuses[collector_id] = status

        return {
            "coordinator_running": self._running,
            "browser_headless": self.headless,
            "total_collectors": len(self.collectors),
            "running_collectors": sum(1 for c in self.collectors.values() if c.is_running()),
            "collectors": collector_statuses,
        }

    async def run_forever(self) -> None:
        """
        Run coordinator until shutdown signal received.

        Useful for long-running processes.
        """
        logger.info("Coordinator running... Press Ctrl+C to stop")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._handle_shutdown())
            )

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        logger.info("Shutdown signal received")

    async def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Initiating graceful shutdown...")
        self._shutdown_event.set()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
        return False


async def create_coordinator(
    headless: bool | None = None,
    auto_init: bool = True
) -> CollectorCoordinator:
    """
    Create and optionally initialize a coordinator.

    Args:
        headless: Run browsers in headless mode
        auto_init: Automatically initialize coordinator

    Returns:
        CollectorCoordinator instance

    Example:
        coordinator = await create_coordinator()
        await coordinator.add_live_tracker('football')
    """
    coordinator = CollectorCoordinator(headless=headless)

    if auto_init:
        await coordinator.initialize()

    return coordinator
