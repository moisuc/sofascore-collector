"""Example usage of the orchestrator module."""

import asyncio
import logging
from datetime import date, timedelta

from src.orchestrator import create_coordinator
from src.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Example 1: Basic Live Tracking for Multiple Sports
async def example_multiple_live_trackers():
    """Example: Track live matches for multiple sports simultaneously."""
    logger.info("=== Example 1: Multiple Live Trackers ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Start live trackers for all configured sports
        trackers = await coordinator.add_live_trackers_for_all_sports()

        logger.info(f"Started {len(trackers)} live trackers")

        # Show status
        status = coordinator.get_status()
        logger.info(f"Status: {status}")

        # Run for 2 minutes
        await asyncio.sleep(120)

    finally:
        await coordinator.cleanup()

    logger.info("Example 1 complete")


# Example 2: Selective Live Tracking
async def example_selective_live_tracking():
    """Example: Track live matches for specific sports only."""
    logger.info("=== Example 2: Selective Live Tracking ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Add live trackers for specific sports
        await coordinator.add_live_tracker("football")
        await coordinator.add_live_tracker("tennis")

        logger.info("Started live trackers for football and tennis")

        # Check status
        status = coordinator.get_status()
        for collector_id, collector_status in status["collectors"].items():
            logger.info(
                f"{collector_id}: running={collector_status['running']}, "
                f"sport={collector_status['sport']}"
            )

        # Run for 1 minute
        await asyncio.sleep(60)

    finally:
        await coordinator.cleanup()

    logger.info("Example 2 complete")


# Example 3: Collect Upcoming Matches
async def example_collect_upcoming():
    """Example: Collect upcoming matches for next 7 days."""
    logger.info("=== Example 3: Collect Upcoming Matches ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Collect upcoming tennis matches
        collector = await coordinator.collect_upcoming_matches(
            sport="tennis",
            days_ahead=7
        )

        logger.info("Started collecting upcoming tennis matches (next 7 days)")

        # Monitor progress
        while collector.is_running():
            progress = collector.get_progress()
            logger.info(
                f"Progress: {progress['processed_days']}/{progress['total_days']} days "
                f"({progress['progress_percent']:.1f}%)"
            )
            await asyncio.sleep(5)

        logger.info("Collection complete!")

    finally:
        await coordinator.cleanup()

    logger.info("Example 3 complete")


# Example 4: Historical Backfill
async def example_historical_backfill():
    """Example: Backfill historical data for the last 30 days."""
    logger.info("=== Example 4: Historical Backfill ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Backfill last 30 days of football matches
        collector = await coordinator.backfill_historical_data(
            sport="football",
            days_back=30
        )

        logger.info("Started backfilling football data (last 30 days)")

        # Monitor progress
        while collector.is_running():
            progress = collector.get_progress()
            logger.info(
                f"Backfill progress: {progress['processed_days']}/{progress['total_days']} days "
                f"({progress['progress_percent']:.1f}%)"
            )
            await asyncio.sleep(10)

        logger.info("Backfill complete!")

    finally:
        await coordinator.cleanup()

    logger.info("Example 4 complete")


# Example 5: Mixed Collectors (Live + Daily)
async def example_mixed_collectors():
    """Example: Run live trackers AND daily collectors simultaneously."""
    logger.info("=== Example 5: Mixed Collectors ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Start live tracker for football
        await coordinator.add_live_tracker("football")
        logger.info("Started live football tracker")

        # Collect upcoming basketball matches
        await coordinator.collect_upcoming_matches("basketball", days_ahead=3)
        logger.info("Started collecting upcoming basketball matches")

        # Backfill tennis data
        await coordinator.backfill_historical_data("tennis", days_back=7)
        logger.info("Started backfilling tennis data")

        # Show status
        status = coordinator.get_status()
        logger.info(f"Total collectors: {status['total_collectors']}")
        logger.info(f"Running collectors: {status['running_collectors']}")

        # Run for a while
        await asyncio.sleep(60)

        # Check status again
        status = coordinator.get_status()
        for collector_id, collector_status in status["collectors"].items():
            logger.info(f"{collector_id}: {collector_status}")

    finally:
        await coordinator.cleanup()

    logger.info("Example 5 complete")


# Example 6: Manual Collector Management
async def example_manual_management():
    """Example: Manually start and stop collectors."""
    logger.info("=== Example 6: Manual Collector Management ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Add live tracker but don't auto-start
        tracker = await coordinator.add_live_tracker("volleyball", auto_start=False)
        logger.info("Added volleyball tracker (not started)")

        # Start it manually
        await tracker.start()
        logger.info("Started volleyball tracker manually")

        # Run for 30 seconds
        await asyncio.sleep(30)

        # Stop specific collector
        await coordinator.stop_collector("live_volleyball")
        logger.info("Stopped volleyball tracker")

        # Add another collector
        await coordinator.add_live_tracker("handball")
        logger.info("Added handball tracker")

        # Run for another 30 seconds
        await asyncio.sleep(30)

    finally:
        await coordinator.cleanup()

    logger.info("Example 6 complete")


# Example 7: Custom Date Range Collection
async def example_custom_date_range():
    """Example: Collect matches for a custom date range."""
    logger.info("=== Example 7: Custom Date Range Collection ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Collect matches for specific date range
        start = date.today() - timedelta(days=3)
        end = date.today() + timedelta(days=3)

        collector = await coordinator.add_daily_collector(
            sport="basketball",
            start_date=start,
            end_date=end,
            backfill_mode=False,
            auto_start=True,
        )

        logger.info(f"Collecting basketball matches from {start} to {end}")

        # Wait for completion
        while collector.is_running():
            progress = collector.get_progress()
            logger.info(f"Progress: {progress['progress_percent']:.1f}%")
            await asyncio.sleep(5)

        logger.info("Collection complete!")

    finally:
        await coordinator.cleanup()

    logger.info("Example 7 complete")


# Example 8: Status Monitoring
async def example_status_monitoring():
    """Example: Monitor coordinator status in real-time."""
    logger.info("=== Example 8: Status Monitoring ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Start multiple collectors
        await coordinator.add_live_tracker("football")
        await coordinator.add_live_tracker("tennis")
        await coordinator.collect_upcoming_matches("basketball", days_ahead=2)

        # Monitor status every 10 seconds
        for i in range(6):  # 1 minute total
            status = coordinator.get_status()

            logger.info("=" * 50)
            logger.info(f"Coordinator Running: {status['coordinator_running']}")
            logger.info(f"Headless Mode: {status['browser_headless']}")
            logger.info(f"Total Collectors: {status['total_collectors']}")
            logger.info(f"Running Collectors: {status['running_collectors']}")

            for collector_id, collector_status in status["collectors"].items():
                logger.info(f"  {collector_id}:")
                logger.info(f"    Running: {collector_status['running']}")
                logger.info(f"    Type: {collector_status['type']}")
                logger.info(f"    Sport: {collector_status['sport']}")

                if "progress" in collector_status:
                    progress = collector_status["progress"]
                    logger.info(f"    Progress: {progress['progress_percent']:.1f}%")

            logger.info("=" * 50)

            await asyncio.sleep(10)

    finally:
        await coordinator.cleanup()

    logger.info("Example 8 complete")


# Example 9: Schedule Window Collection (Single Sport)
async def example_schedule_window():
    """Example: Collect schedule window (past + future) for a single sport."""
    logger.info("=== Example 9: Schedule Window Collection ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Collect past 3 days + today + future 3 days for football
        collector = await coordinator.collect_schedule_window(
            sport="football",
            days_past=3,
            days_future=3
        )

        logger.info("Started schedule window collection for football (7 days total)")

        # Monitor progress
        while collector.is_running():
            progress = collector.get_progress()
            logger.info(
                f"Progress: {progress['processed_days']}/{progress['total_days']} days "
                f"({progress['progress_percent']:.1f}%) - "
                f"{progress['start_date']} to {progress['end_date']}"
            )
            await asyncio.sleep(5)

        logger.info("Schedule window collection complete!")

    finally:
        await coordinator.cleanup()

    logger.info("Example 9 complete")


# Example 10: Schedule Window for All Sports
async def example_schedule_window_all_sports():
    """Example: Collect schedule window for all configured sports."""
    logger.info("=== Example 10: Schedule Window for All Sports ===")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Collect 7-day window for all sports (past 3 + today + future 3)
        logger.info(f"Collecting schedule window for: {settings.sports}")

        collectors = await coordinator.collect_schedule_window_for_all_sports(
            days_past=3,
            days_future=3
        )

        logger.info(f"Completed schedule window collection for {len(collectors)} sports")

        # Show final status
        status = coordinator.get_status()
        for collector_id, collector_status in status["collectors"].items():
            if "progress" in collector_status:
                progress = collector_status["progress"]
                logger.info(
                    f"{collector_status['sport']}: "
                    f"{progress['processed_days']}/{progress['total_days']} days "
                    f"({progress['progress_percent']:.1f}%)"
                )

    finally:
        await coordinator.cleanup()

    logger.info("Example 10 complete")


async def main():
    """Run all examples."""
    logger.info("Starting Orchestrator Examples")

    # Run one example at a time (comment out the ones you don't want to run)

    # Example 1: Multiple live trackers
    # await example_multiple_live_trackers()

    # Example 2: Selective live tracking
    # await example_selective_live_tracking()

    # Example 3: Collect upcoming matches
    # await example_collect_upcoming()

    # Example 4: Historical backfill
    # await example_historical_backfill()

    # Example 5: Mixed collectors
    # await example_mixed_collectors()

    # Example 6: Manual management
    # await example_manual_management()

    # Example 7: Custom date range
    # await example_custom_date_range()

    # Example 8: Status monitoring
    # await example_status_monitoring()

    # Example 9: Schedule window (single sport)
    # await example_schedule_window()

    # Example 10: Schedule window for all sports
    await example_schedule_window_all_sports()

    logger.info("All examples complete!")


if __name__ == "__main__":
    asyncio.run(main())
