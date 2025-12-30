"""Database session pooling with lifecycle management."""

import asyncio
import logging
import time
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.storage.database import get_session as create_new_session

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    """Metrics for a session in the pool."""

    session_id: int
    created_at: float = field(default_factory=time.time)
    last_acquired: float = field(default_factory=time.time)
    last_released: float = field(default_factory=time.time)
    acquire_count: int = 0
    in_use: bool = False

    @property
    def idle_time(self) -> float:
        """Get time since last release (in seconds)."""
        if self.in_use:
            return 0.0
        return time.time() - self.last_released

    @property
    def age(self) -> float:
        """Get total age of session (in seconds)."""
        return time.time() - self.created_at


class ManagedSession:
    """
    Wrapper around SQLAlchemy Session with automatic lifecycle management.

    Provides context manager interface that automatically returns
    session to pool on exit, even if exceptions occur.

    Usage:
        async with session_pool.acquire() as session:
            # Use session for database operations
            session.query(Match).all()
            session.commit()
        # Session automatically returned to pool
    """

    def __init__(
        self,
        session: Session,
        pool: "SessionPool",
        session_id: int,
        metrics: SessionMetrics
    ):
        """
        Initialize managed session.

        Args:
            session: Underlying SQLAlchemy session
            pool: Parent pool to return to
            session_id: Unique identifier for this session
            metrics: Metrics tracking object
        """
        self._session = session
        self._pool = pool
        self._session_id = session_id
        self._metrics = metrics
        self._released = False

    @property
    def session(self) -> Session:
        """Get underlying SQLAlchemy session."""
        return self._session

    @property
    def session_id(self) -> int:
        """Get session ID."""
        return self._session_id

    async def __aenter__(self) -> Session:
        """
        Enter context manager.

        Returns:
            Underlying SQLAlchemy session
        """
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Exit context manager and return session to pool.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value
            exc_tb: Exception traceback

        Returns:
            False to propagate exceptions
        """
        if not self._released:
            try:
                # Rollback on error, otherwise assume commit happened in handler
                if exc_type is not None:
                    self._session.rollback()
                    logger.debug(
                        f"Session {self._session_id} rolled back due to {exc_type.__name__}"
                    )

                # Return to pool
                await self._pool.release(self)
                self._released = True

            except Exception as e:
                logger.error(f"Error releasing session {self._session_id}: {e}", exc_info=True)

        # Don't suppress exceptions
        return False

    async def release(self) -> None:
        """Manually release session back to pool."""
        if not self._released:
            await self._pool.release(self)
            self._released = True


class SessionPool:
    """
    Pool of SQLAlchemy sessions with lifecycle management.

    Features:
    - Configurable max pool size
    - Automatic session creation and cleanup
    - Idle session timeout and cleanup
    - Metrics tracking (acquire count, idle time, etc.)
    - Thread-safe for async usage

    Example:
        pool = SessionPool(max_size=10, idle_timeout=300.0)
        await pool.initialize()

        async with pool.acquire() as session:
            matches = session.query(Match).all()

        await pool.cleanup()
    """

    def __init__(
        self,
        max_size: int = 10,
        idle_timeout: float = 300.0,
        min_size: int = 2,
        acquire_timeout: float = 30.0
    ):
        """
        Initialize session pool.

        Args:
            max_size: Maximum number of sessions in pool
            idle_timeout: Seconds before idle session is closed (default: 5 min)
            min_size: Minimum sessions to keep in pool
            acquire_timeout: Max seconds to wait for available session
        """
        self.max_size = max_size
        self.idle_timeout = idle_timeout
        self.min_size = min_size
        self.acquire_timeout = acquire_timeout

        # Pool state
        self._available: asyncio.Queue[tuple[Session, SessionMetrics]] = asyncio.Queue()
        self._in_use: dict[int, tuple[Session, SessionMetrics]] = {}
        self._session_counter = 0
        self._lock = asyncio.Lock()
        self._initialized = False

        # Metrics
        self._total_created = 0
        self._total_closed = 0
        self._total_acquires = 0
        self._total_releases = 0

    async def initialize(self) -> None:
        """Initialize pool with minimum sessions."""
        if self._initialized:
            logger.warning("SessionPool already initialized")
            return

        logger.info(f"Initializing SessionPool (min: {self.min_size}, max: {self.max_size})")

        # Create minimum sessions and add to available pool
        for _ in range(self.min_size):
            session, metrics = await self._create_session()
            await self._available.put((session, metrics))

        self._initialized = True
        logger.info(f"SessionPool initialized with {self.min_size} sessions")

    async def _create_session(self) -> tuple[Session, SessionMetrics]:
        """
        Create a new session and add to pool.

        Returns:
            Tuple of (Session, SessionMetrics)
        """
        async with self._lock:
            # Check if we've hit max size
            total_sessions = self._available.qsize() + len(self._in_use)
            if total_sessions >= self.max_size:
                raise RuntimeError(
                    f"SessionPool exhausted: {total_sessions}/{self.max_size} sessions in use"
                )

            # Create new session
            session = create_new_session()
            self._session_counter += 1
            session_id = self._session_counter

            metrics = SessionMetrics(session_id=session_id)

            self._total_created += 1
            logger.debug(f"Created session {session_id} (total: {total_sessions + 1}/{self.max_size})")

            return session, metrics

    async def acquire(self) -> ManagedSession:
        """
        Acquire a session from pool.

        If no sessions available and pool not at max size, creates new session.
        If pool is full, waits up to acquire_timeout for a session to be released.

        Returns:
            ManagedSession context manager

        Raises:
            asyncio.TimeoutError: If timeout waiting for available session
            RuntimeError: If pool is exhausted and can't create more
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()

        while True:
            # Try to get available session
            try:
                session, metrics = self._available.get_nowait()

                # Update metrics
                metrics.last_acquired = time.time()
                metrics.acquire_count += 1
                metrics.in_use = True

                # Move to in-use
                async with self._lock:
                    self._in_use[metrics.session_id] = (session, metrics)
                    self._total_acquires += 1

                logger.debug(
                    f"Acquired session {metrics.session_id} "
                    f"(available: {self._available.qsize()}, in_use: {len(self._in_use)})"
                )

                return ManagedSession(session, self, metrics.session_id, metrics)

            except asyncio.QueueEmpty:
                # No available sessions, try to create new one
                try:
                    session, metrics = await self._create_session()

                    # Mark as in use immediately
                    metrics.last_acquired = time.time()
                    metrics.acquire_count += 1
                    metrics.in_use = True

                    async with self._lock:
                        self._in_use[metrics.session_id] = (session, metrics)
                        self._total_acquires += 1

                    logger.debug(
                        f"Created and acquired new session {metrics.session_id} "
                        f"(available: {self._available.qsize()}, in_use: {len(self._in_use)})"
                    )

                    return ManagedSession(session, self, metrics.session_id, metrics)

                except RuntimeError:
                    # Pool is full, wait for release
                    elapsed = time.time() - start_time
                    if elapsed >= self.acquire_timeout:
                        raise asyncio.TimeoutError(
                            f"Timeout acquiring session after {elapsed:.2f}s "
                            f"(in_use: {len(self._in_use)}/{self.max_size})"
                        )

                    # Wait a bit and retry
                    await asyncio.sleep(0.1)

    async def release(self, managed_session: ManagedSession) -> None:
        """
        Release session back to pool.

        Args:
            managed_session: ManagedSession to release
        """
        session_id = managed_session.session_id

        async with self._lock:
            if session_id not in self._in_use:
                logger.warning(f"Attempted to release unknown session {session_id}")
                return

            session, metrics = self._in_use.pop(session_id)

            # Update metrics
            metrics.last_released = time.time()
            metrics.in_use = False

            # Check if session is still healthy
            try:
                # Simple health check - verify session is not closed
                if not session.is_active:
                    logger.warning(f"Session {session_id} is not active, closing instead of pooling")
                    session.close()
                    self._total_closed += 1
                    return

                # Return to available pool
                await self._available.put((session, metrics))
                self._total_releases += 1

                logger.debug(
                    f"Released session {session_id} "
                    f"(available: {self._available.qsize()}, in_use: {len(self._in_use)})"
                )

            except Exception as e:
                logger.error(f"Error checking session {session_id} health: {e}", exc_info=True)
                # Close problematic session
                try:
                    session.close()
                    self._total_closed += 1
                except Exception:
                    pass

    async def cleanup_idle(self, max_idle_time: Optional[float] = None) -> int:
        """
        Close idle sessions that have exceeded timeout.

        Keeps at least min_size sessions in pool.

        Args:
            max_idle_time: Override idle timeout (uses self.idle_timeout if None)

        Returns:
            Number of sessions closed
        """
        if max_idle_time is None:
            max_idle_time = self.idle_timeout

        closed_count = 0
        sessions_to_keep = []

        # Check all available sessions
        while not self._available.empty():
            try:
                session, metrics = self._available.get_nowait()

                # Keep if within idle timeout or pool is at minimum
                current_pool_size = len(sessions_to_keep) + len(self._in_use)

                if metrics.idle_time < max_idle_time or current_pool_size < self.min_size:
                    sessions_to_keep.append((session, metrics))
                else:
                    # Close idle session
                    try:
                        session.close()
                        closed_count += 1
                        self._total_closed += 1
                        logger.debug(
                            f"Closed idle session {metrics.session_id} "
                            f"(idle: {metrics.idle_time:.1f}s, age: {metrics.age:.1f}s)"
                        )
                    except Exception as e:
                        logger.error(f"Error closing session {metrics.session_id}: {e}")

            except asyncio.QueueEmpty:
                break

        # Return kept sessions to pool
        for session, metrics in sessions_to_keep:
            await self._available.put((session, metrics))

        if closed_count > 0:
            logger.info(
                f"Cleanup closed {closed_count} idle sessions "
                f"(available: {self._available.qsize()}, in_use: {len(self._in_use)})"
            )

        return closed_count

    async def cleanup(self) -> None:
        """Close all sessions and cleanup pool."""
        logger.info("Cleaning up SessionPool...")

        closed_count = 0

        # Close in-use sessions (should not happen normally)
        async with self._lock:
            for session_id, (session, metrics) in list(self._in_use.items()):
                try:
                    session.close()
                    closed_count += 1
                    logger.warning(f"Closed in-use session {session_id} during cleanup")
                except Exception as e:
                    logger.error(f"Error closing in-use session {session_id}: {e}")

            self._in_use.clear()

        # Close available sessions
        while not self._available.empty():
            try:
                session, metrics = self._available.get_nowait()
                session.close()
                closed_count += 1
            except Exception as e:
                logger.error(f"Error closing available session: {e}")

        self._total_closed += closed_count
        self._initialized = False

        logger.info(
            f"SessionPool cleanup complete: closed {closed_count} sessions "
            f"(total created: {self._total_created}, total closed: {self._total_closed})"
        )

    def get_metrics(self) -> dict:
        """
        Get pool metrics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            "pool_size": {
                "max": self.max_size,
                "min": self.min_size,
                "available": self._available.qsize(),
                "in_use": len(self._in_use),
                "total": self._available.qsize() + len(self._in_use),
            },
            "lifetime": {
                "total_created": self._total_created,
                "total_closed": self._total_closed,
                "total_acquires": self._total_acquires,
                "total_releases": self._total_releases,
            },
            "config": {
                "idle_timeout": self.idle_timeout,
                "acquire_timeout": self.acquire_timeout,
            },
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
        return False
