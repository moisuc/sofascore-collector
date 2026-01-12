"""Main entry point for SofaScore data collector."""

import argparse
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


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="SofaScore data collector - Live sports tracking and match collection"
    )

    parser.add_argument(
        "--collect-upcoming",
        type=int,
        nargs="?",
        const=7,
        metavar="DAYS",
        help="Collect upcoming matches for all sports (default: 7 days ahead if flag is set)",
    )

    parser.add_argument(
        "--collect-schedule-past",
        type=int,
        metavar="DAYS",
        help="Collect past matches in schedule window (requires --collect-schedule-future)",
    )

    parser.add_argument(
        "--collect-schedule-future",
        type=int,
        metavar="DAYS",
        help="Collect future matches in schedule window (requires --collect-schedule-past)",
    )

    return parser.parse_args()


async def main():
    """
    Main function to run the SofaScore collector.

    This function:
    1. Initializes the coordinator
    2. Starts live trackers for all configured sports
    3. Optionally collects upcoming matches (if --collect-upcoming is set)
    4. Optionally collects schedule window (if --collect-schedule-* are set)
    5. Runs until interrupted (Ctrl+C)
    6. Performs graceful shutdown
    """
    args = parse_args()

    logger.info("Starting SofaScore Collector")
    logger.info(f"Configured sports: {settings.sports}")
    logger.info(f"Headless mode: {settings.headless}")

    coordinator = await create_coordinator(headless=settings.headless)
    should_run_forever = True  # Always run forever in this main script
    try:
        if args.collect_upcoming is None and \
           args.collect_schedule_past is None and \
           args.collect_schedule_future is None:
            logger.info("No collection arguments provided, starting live trackers for all sports...")
            trackers = await coordinator.add_live_trackers_for_all_sports()
            logger.info(f"Successfully started {len(trackers)} live trackers")
        # Start live trackers for all configured sports
        # logger.info("Starting live trackers for all sports...")
        # trackers = await coordinator.add_live_trackers_for_all_sports()

        # logger.info(f"Successfully started {len(trackers)} live trackers")

        # Optional: Collect upcoming matches for each sport
        if args.collect_upcoming is not None:
            logger.info(f"Collecting upcoming matches ({args.collect_upcoming} days ahead) for all sports...")
            for sport in settings.sports:
                await coordinator.collect_upcoming_matches(sport, days_ahead=args.collect_upcoming)
            logger.info("Upcoming matches collection complete")
            should_run_forever = True  # Exit after collecting upcoming matches
        # Optional: Collect schedule window (past + future) for all sports
        if args.collect_schedule_past is not None and args.collect_schedule_future is not None:
            logger.info(
                f"Collecting schedule window for all sports "
                f"({args.collect_schedule_past} days past, {args.collect_schedule_future} days future)..."
            )
            await coordinator.collect_schedule_window_for_all_sports(
                days_past=args.collect_schedule_past,
                days_future=args.collect_schedule_future
            )
            logger.info("Schedule window collection complete")
            should_run_forever = True  # Exit after collecting schedule window
        elif args.collect_schedule_past is not None or args.collect_schedule_future is not None:
            logger.warning(
                "Both --collect-schedule-past and --collect-schedule-future must be specified. "
                "Skipping schedule window collection."
            )

        # Show status
        status = coordinator.get_status()
        logger.info(f"Coordinator status: {status['running_collectors']}/{status['total_collectors']} collectors running")
        if should_run_forever:
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
