"""Example usage of the browser module."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path (must be before imports)
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.browser import BrowserManager, create_interceptor, create_ws_interceptor  # noqa: E402
from src.config import settings  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def handle_live_matches(data: dict, match) -> None:
    """Handle live matches data."""
    sport = match.group(1)
    events = data.get('scheduled', [])
    logger.info(f"Received {len(events)} live matches for {sport}")


async def handle_event_details(data: dict, match) -> None:
    """Handle event details."""
    event_id = match.group(1)
    event = data.get('scheduled', {})
    logger.info(f"Event {event_id}: {event.get('homeTeam', {}).get('name')} vs {event.get('awayTeam', {}).get('name')}")


async def handle_ws_message(data: dict) -> None:
    """Handle WebSocket messages."""
    msg_type = data.get('type', 'unknown')
    logger.info(f"WebSocket message: {msg_type}")


async def main():
    """Main example function."""
    # Create browser manager using context manager
    async with BrowserManager(headless=settings.headless) as browser_manager:

        # Create a context for football
        context = await browser_manager.create_context("football")

        # Create a new page
        page = await browser_manager.new_page("football")

        # Create and attach HTTP response interceptor
        http_interceptor = await create_interceptor(page)
        http_interceptor.on('live', handle_live_matches)
        http_interceptor.on('scheduled', handle_event_details)

        # Create and attach WebSocket interceptor
        ws_interceptor = await create_ws_interceptor(page, live_score_mode=True)
        ws_interceptor.on_message(handle_ws_message)

        # Navigate to SofaScore live page
        logger.info("Navigating to SofaScore football live page...")
        await page.goto(
            'https://www.sofascore.com/',
            wait_until='networkidle',
            timeout=30000
        )

        # Start periodic refresh (every 5 minutes)
        await browser_manager.refresh_page_periodically(
            page,
            interval=settings.page_refresh_interval,
            context_name="football"
        )

        # Keep running for 30 seconds to collect data
        logger.info("Collecting data for 30 seconds...")
        await asyncio.sleep(30)

        logger.info(f"Active WebSocket connections: {ws_interceptor.active_connections}")

    logger.info("Browser manager closed")


if __name__ == "__main__":
    asyncio.run(main())
