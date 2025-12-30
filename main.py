"""Main entry point for SofaScore data collector."""

import asyncio
import logging

from src.orchestrator import create_coordinator
from src.config import settings


# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """
    Main function to run the SofaScore collector.

    This function:
    1. Initializes the coordinator
    2. Starts live trackers for all configured sports
    3. Runs until interrupted (Ctrl+C)
    4. Performs graceful shutdown
    """
    logger.info("Starting SofaScore Collector")
    logger.info(f"Configured sports: {settings.sports}")
    logger.info(f"Headless mode: {settings.headless}")

    coordinator = await create_coordinator(headless=settings.headless)

    try:
        # Start live trackers for all configured sports
        logger.info("Starting live trackers for all sports...")
        trackers = await coordinator.add_live_trackers_for_all_sports()
    
        logger.info(f"Successfully started {len(trackers)} live trackers")

        # Optional: Collect upcoming matches for each sport
        # Uncomment to enable:
        # for sport in settings.sports:
        #     await coordinator.collect_upcoming_matches(sport, days_ahead=7)

        # Optional: Collect schedule window (past + future) for all sports
        # This collects historical and upcoming matches in a single operation
        # Uncomment to enable:
        logger.info("Collecting schedule window for all sports...")
        await coordinator.collect_schedule_window_for_all_sports(
            days_past=3,   # Past 3 days
            days_future=3  # Future 3 days
        )
        logger.info("Schedule window collection complete")

        # Show status
        status = coordinator.get_status()
        logger.info(f"Coordinator status: {status['running_collectors']}/{status['total_collectors']} collectors running")

        # Run until interrupted
        await coordinator.run_forever()

    finally:
        await coordinator.cleanup()

    logger.info("SofaScore Collector stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
