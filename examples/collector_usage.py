"""Example usage of the collectors module."""

import asyncio
import logging
from datetime import date, timedelta

from src.browser.manager import BrowserManager
from src.collectors import LiveTracker, DailyEventsCollector
from src.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Example 1: Live Football Tracker
async def example_live_tracker():
    """Example: Track live football matches."""
    logger.info("=== Example 1: Live Football Tracker ===")

    async def handle_live_data(data: dict, match) -> None:
        """Handle live match data."""
        events = data.get("events", [])
        logger.info(f"Live football matches: {len(events)}")

        for event in events[:3]:  # Show first 3
            home_team = event.get("homeTeam", {}).get("name", "Unknown")
            away_team = event.get("awayTeam", {}).get("name", "Unknown")
            score = event.get("homeScore", {}).get("current", 0)
            score_away = event.get("awayScore", {}).get("current", 0)
            logger.info(f"  {home_team} {score} - {score_away} {away_team}")

    async def handle_score_update(data: dict) -> None:
        """Handle WebSocket score updates."""
        logger.info(f"Score update: {data.get('type', 'unknown')}")

    async with BrowserManager(headless=settings.headless) as browser_manager:
        # Create live tracker for football
        tracker = LiveTracker(
            browser_manager,
            sport="football",
            on_live_data=handle_live_data,
            on_score_update=handle_score_update,
        )

        await tracker.start()

        # Run for 2 minutes
        await asyncio.sleep(120)

        await tracker.stop()

    logger.info("Live tracker example complete")


# Example 2: Daily Events Collector - Upcoming Matches
async def example_daily_collector_upcoming():
    """Example: Collect upcoming tennis matches for the next 3 days."""
    logger.info("=== Example 2: Daily Events - Upcoming Tennis ===")

    async def handle_scheduled_data(data: dict, match) -> None:
        """Handle scheduled match data."""
        events = data.get("events", [])
        date_str = match.group(2) if match.lastindex >= 2 else "unknown"
        logger.info(f"Scheduled tennis matches on {date_str}: {len(events)}")

        for event in events[:3]:  # Show first 3
            home_team = event.get("homeTeam", {}).get("name", "Unknown")
            away_team = event.get("awayTeam", {}).get("name", "Unknown")
            start_time = event.get("startTimestamp", "N/A")
            logger.info(f"  {home_team} vs {away_team} (starts: {start_time})")

    async with BrowserManager(headless=settings.headless) as browser_manager:
        # Collect next 3 days of tennis matches
        collector = DailyEventsCollector(
            browser_manager,
            sport="tennis",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            on_scheduled_data=handle_scheduled_data,
            backfill_mode=False,
        )

        await collector.start()

        # Wait for completion
        while collector.is_running():
            progress = collector.get_progress()
            logger.info(
                f"Progress: {progress['processed_days']}/{progress['total_days']} "
                f"({progress['progress_percent']:.1f}%)"
            )
            await asyncio.sleep(5)

    logger.info("Daily collector (upcoming) example complete")


# Example 3: Daily Events Collector - Historical Backfill
async def example_daily_collector_backfill():
    """Example: Backfill historical basketball matches."""
    logger.info("=== Example 3: Daily Events - Historical Basketball ===")

    matches_collected = []

    async def handle_scheduled_data(data: dict, match) -> None:
        """Handle scheduled match data and store it."""
        events = data.get("events", [])
        date_str = match.group(2) if match.lastindex >= 2 else "unknown"
        logger.info(f"Backfilling basketball matches on {date_str}: {len(events)}")

        # Store matches for later processing
        matches_collected.extend(events)

    async with BrowserManager(headless=settings.headless) as browser_manager:
        # Backfill last 7 days
        start = date.today() - timedelta(days=7)
        end = date.today() - timedelta(days=1)

        collector = DailyEventsCollector(
            browser_manager,
            sport="basketball",
            start_date=start,
            end_date=end,
            on_scheduled_data=handle_scheduled_data,
            backfill_mode=True,  # Use backfill delays
        )

        await collector.start()

        # Wait for completion
        while collector.is_running():
            await asyncio.sleep(2)

    logger.info(
        f"Historical backfill complete. Total matches collected: {len(matches_collected)}"
    )


# Example 4: Multiple Live Trackers (Multiple Sports)
async def example_multiple_trackers():
    """Example: Track multiple sports simultaneously."""
    logger.info("=== Example 4: Multiple Live Trackers ===")

    async def create_handler(sport_name: str):
        """Create a handler for a specific sport."""

        async def handler(data: dict, match) -> None:
            events = data.get("events", [])
            logger.info(f"[{sport_name.upper()}] Live matches: {len(events)}")

        return handler

    async with BrowserManager(headless=settings.headless) as browser_manager:
        # Create trackers for multiple sports
        trackers = []

        for sport in ["football", "tennis", "basketball"]:
            tracker = LiveTracker(
                browser_manager,
                sport=sport,
                on_live_data=await create_handler(sport),
            )
            await tracker.start()
            trackers.append(tracker)

        # Run all trackers for 1 minute
        logger.info("Running 3 live trackers simultaneously...")
        await asyncio.sleep(60)

        # Stop all trackers
        for tracker in trackers:
            await tracker.stop()

    logger.info("Multiple trackers example complete")


# Example 5: Using Context Manager
async def example_context_manager():
    """Example: Use collectors with context managers."""
    logger.info("=== Example 5: Context Manager Usage ===")

    async def handle_live(data: dict, match) -> None:
        events = data.get("events", [])
        logger.info(f"Volleyball live matches: {len(events)}")

    async with BrowserManager(headless=settings.headless) as browser_manager:
        # Use LiveTracker as context manager
        async with LiveTracker(
            browser_manager, sport="volleyball", on_live_data=handle_live
        ) as tracker:
            logger.info("Tracker started automatically")
            await asyncio.sleep(30)
            # Tracker will stop automatically when exiting context

    logger.info("Context manager example complete")


async def main():
    """Run all examples."""
    logger.info("Starting SofaScore Collectors Examples")

    # Run examples one by one (comment out the ones you don't want to run)

    # Example 1: Live tracker
    # await example_live_tracker()

    # Example 2: Daily collector - upcoming matches
    # await example_daily_collector_upcoming()

    # Example 3: Daily collector - historical backfill
    # await example_daily_collector_backfill()

    # Example 4: Multiple trackers
    # await example_multiple_trackers()

    # Example 5: Context manager
    await example_context_manager()

    logger.info("All examples complete!")


if __name__ == "__main__":
    asyncio.run(main())
