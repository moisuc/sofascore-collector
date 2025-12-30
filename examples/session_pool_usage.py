"""Example usage of SessionPool for memory-efficient database operations."""

import asyncio
import logging

from src.memory import SessionPool
from src.config import settings
from src.storage.database import init_db, Match, Team, League
from src.storage.repositories import MatchRepository, TeamRepository

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Basic usage of SessionPool."""
    logger.info("=== Basic SessionPool Usage ===")

    # Initialize database
    init_db()

    # Create session pool with custom settings
    async with SessionPool(
        max_size=settings.max_db_sessions,
        min_size=settings.min_db_sessions,
        idle_timeout=settings.session_idle_timeout,
        acquire_timeout=settings.session_acquire_timeout,
    ) as pool:
        # Get metrics
        metrics = pool.get_metrics()
        logger.info(f"Pool initialized: {metrics}")

        # Acquire and use a session (manual)
        managed_session = await pool.acquire()
        async with managed_session as session:
            # Use session for queries
            team_repo = TeamRepository(session)
            teams = team_repo.list(limit=5)
            logger.info(f"Found {len(teams)} teams")

        # Session automatically returned to pool

        # Check metrics after usage
        metrics = pool.get_metrics()
        logger.info(f"After first query: {metrics}")


async def example_concurrent_queries():
    """Multiple concurrent queries using the pool."""
    logger.info("\n=== Concurrent Queries Example ===")

    init_db()

    async with SessionPool(max_size=5, min_size=2) as pool:

        async def query_matches():
            """Query matches in separate task."""
            managed = await pool.acquire()
            async with managed as session:
                match_repo = MatchRepository(session)
                matches = match_repo.list(limit=10)
                logger.info(f"Task found {len(matches)} matches")
                await asyncio.sleep(0.1)  # Simulate work

        async def query_teams():
            """Query teams in separate task."""
            managed = await pool.acquire()
            async with managed as session:
                team_repo = TeamRepository(session)
                teams = team_repo.list(limit=10)
                logger.info(f"Task found {len(teams)} teams")
                await asyncio.sleep(0.1)  # Simulate work

        # Run multiple queries concurrently
        tasks = [
            query_matches(),
            query_teams(),
            query_matches(),
            query_teams(),
        ]

        await asyncio.gather(*tasks)

        # Check final metrics
        metrics = pool.get_metrics()
        logger.info(f"Final metrics: {metrics}")


async def example_error_handling():
    """Error handling with automatic rollback."""
    logger.info("\n=== Error Handling Example ===")

    init_db()

    async with SessionPool(max_size=3) as pool:
        managed = await pool.acquire()

        try:
            async with managed as session:
                # Simulate error during transaction
                team_repo = TeamRepository(session)
                logger.info("Querying teams...")
                teams = team_repo.list(limit=1)

                # Simulate error
                raise ValueError("Simulated error!")
        except ValueError as e:
            logger.info(f"Error caught: {e}")
            logger.info("Session automatically rolled back and returned to pool")

        # Pool should still be healthy
        metrics = pool.get_metrics()
        logger.info(f"Pool is healthy: {metrics}")


async def example_cleanup_monitoring():
    """Monitor pool cleanup behavior."""
    logger.info("\n=== Cleanup Monitoring Example ===")

    init_db()

    pool = SessionPool(
        max_size=5,
        min_size=2,
        idle_timeout=2.0,  # Short timeout for demo
    )
    await pool.initialize()

    try:
        # Create some sessions
        sessions = []
        for i in range(4):
            s = await pool.acquire()
            sessions.append(s)
            logger.info(f"Acquired session {i+1}")

        # Release all
        for s in sessions:
            await s.release()

        logger.info(f"All sessions released")
        metrics = pool.get_metrics()
        logger.info(f"Metrics: {metrics}")

        # Wait for idle timeout
        logger.info("Waiting 3 seconds for idle timeout...")
        await asyncio.sleep(3)

        # Run cleanup
        closed = await pool.cleanup_idle()
        logger.info(f"Cleanup closed {closed} idle sessions")

        # Check final pool size (should respect min_size)
        metrics = pool.get_metrics()
        logger.info(f"Final pool size: {metrics['pool_size']}")
        assert metrics["pool_size"]["available"] >= pool.min_size

    finally:
        await pool.cleanup()


async def example_pool_exhaustion():
    """Demonstrate pool exhaustion and waiting."""
    logger.info("\n=== Pool Exhaustion Example ===")

    init_db()

    pool = SessionPool(max_size=3, min_size=1, acquire_timeout=2.0)
    await pool.initialize()

    try:
        # Acquire all sessions
        sessions = []
        for i in range(3):
            s = await pool.acquire()
            sessions.append(s)
            logger.info(f"Acquired session {i+1}/3")

        metrics = pool.get_metrics()
        logger.info(f"Pool full: {metrics['pool_size']}")

        # Try to acquire when pool is full (will timeout)
        try:
            logger.info("Trying to acquire when pool is full...")
            await pool.acquire()
            logger.error("Should not reach here!")
        except asyncio.TimeoutError:
            logger.info("Timeout waiting for session (expected)")

        # Release one and try again
        await sessions[0].release()
        logger.info("Released one session")

        # Now this should succeed
        new_session = await pool.acquire()
        logger.info("Successfully acquired session after release")

        # Cleanup
        for s in sessions[1:]:
            await s.release()
        await new_session.release()

    finally:
        await pool.cleanup()


async def main():
    """Run all examples."""
    await example_basic_usage()
    await example_concurrent_queries()
    await example_error_handling()
    await example_cleanup_monitoring()
    await example_pool_exhaustion()

    logger.info("\n=== All Examples Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
