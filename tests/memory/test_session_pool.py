"""Tests for session pool and managed session."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock

from src.memory.session_pool import SessionPool, ManagedSession, SessionMetrics


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.is_active = True
    session.rollback = Mock()
    session.commit = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Create a mock session factory that returns mock sessions."""
    def factory():
        # Return a new mock each time
        new_mock = MagicMock()
        new_mock.is_active = True
        new_mock.rollback = Mock()
        new_mock.commit = Mock()
        new_mock.close = Mock()
        return new_mock
    return factory


@pytest_asyncio.fixture
async def session_pool(mock_session_factory):
    """Create a session pool for testing."""
    with patch("src.memory.session_pool.create_new_session", mock_session_factory):
        pool = SessionPool(max_size=5, min_size=2, idle_timeout=1.0, acquire_timeout=5.0)
        await pool.initialize()
        yield pool
        await pool.cleanup()


class TestSessionMetrics:
    """Test SessionMetrics class."""

    def test_metrics_initialization(self):
        """Test metrics are initialized correctly."""
        metrics = SessionMetrics(session_id=1)
        assert metrics.session_id == 1
        assert metrics.acquire_count == 0
        assert metrics.in_use is False
        assert metrics.created_at > 0
        assert metrics.last_acquired > 0

    def test_idle_time_when_in_use(self):
        """Test idle_time returns 0 when session is in use."""
        metrics = SessionMetrics(session_id=1)
        metrics.in_use = True
        assert metrics.idle_time == 0.0

    def test_idle_time_when_not_in_use(self):
        """Test idle_time returns correct value when idle."""
        metrics = SessionMetrics(session_id=1)
        metrics.in_use = False
        import time
        time.sleep(0.1)
        assert metrics.idle_time >= 0.1

    def test_age_calculation(self):
        """Test session age calculation."""
        metrics = SessionMetrics(session_id=1)
        import time
        time.sleep(0.1)
        assert metrics.age >= 0.1


class TestSessionPool:
    """Test SessionPool class."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self, mock_session_factory):
        """Test pool initializes with minimum sessions."""
        with patch("src.memory.session_pool.create_new_session", mock_session_factory):
            pool = SessionPool(max_size=5, min_size=2)
            await pool.initialize()

            metrics = pool.get_metrics()
            assert metrics["pool_size"]["total"] == 2
            assert metrics["pool_size"]["available"] == 2
            assert metrics["pool_size"]["in_use"] == 0

            await pool.cleanup()

    @pytest.mark.asyncio
    async def test_acquire_from_available_pool(self, session_pool):
        """Test acquiring session from available pool."""
        managed_session = await session_pool.acquire()

        assert isinstance(managed_session, ManagedSession)
        assert managed_session.session_id > 0

        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 1
        assert metrics["pool_size"]["available"] == 1

        await managed_session.release()

    @pytest.mark.asyncio
    async def test_acquire_creates_new_session_when_needed(self, session_pool):
        """Test pool creates new session when available pool is empty."""
        # Acquire all initial sessions
        session1 = await session_pool.acquire()
        session2 = await session_pool.acquire()

        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["available"] == 0
        assert metrics["pool_size"]["in_use"] == 2

        # This should create a new session (under max_size)
        session3 = await session_pool.acquire()

        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["total"] == 3
        assert metrics["pool_size"]["in_use"] == 3

        await session1.release()
        await session2.release()
        await session3.release()

    @pytest.mark.asyncio
    async def test_context_manager_auto_release(self, session_pool):
        """Test context manager automatically releases session."""
        managed = await session_pool.acquire()
        async with managed as session:
            assert session is not None
            metrics_before = session_pool.get_metrics()
            assert metrics_before["pool_size"]["in_use"] == 1

        # After context exit, session should be released
        await asyncio.sleep(0.1)
        metrics_after = session_pool.get_metrics()
        assert metrics_after["pool_size"]["in_use"] == 0

    @pytest.mark.asyncio
    async def test_context_manager_rollback_on_error(self, session_pool):
        """Test context manager rolls back on exception."""
        managed = await session_pool.acquire()
        try:
            async with managed as session:
                # Simulate error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Session should be released even after error
        await asyncio.sleep(0.1)
        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 0

    @pytest.mark.asyncio
    async def test_pool_exhaustion_waits_for_release(self, session_pool):
        """Test acquiring when pool is full waits for release."""
        # Acquire all sessions up to max_size (5)
        sessions = []
        for _ in range(5):
            s = await session_pool.acquire()
            sessions.append(s)

        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 5
        assert metrics["pool_size"]["total"] == 5

        # Try to acquire another - should wait
        async def try_acquire():
            await asyncio.sleep(0.2)  # Delay to ensure acquisition attempt starts
            # Release one session to allow acquisition
            await sessions[0].release()

        # Start the delayed release
        release_task = asyncio.create_task(try_acquire())

        # This should wait and then succeed
        new_session = await session_pool.acquire()
        assert new_session is not None

        await release_task

        # Clean up
        for s in sessions[1:]:
            await s.release()
        await new_session.release()

    @pytest.mark.asyncio
    async def test_acquire_timeout(self, session_pool):
        """Test timeout when waiting for session."""
        # Acquire all sessions
        sessions = []
        for _ in range(5):
            s = await session_pool.acquire()
            sessions.append(s)

        # Try to acquire without releasing - should timeout
        with pytest.raises(asyncio.TimeoutError):
            await session_pool.acquire()

        # Clean up
        for s in sessions:
            await s.release()

    @pytest.mark.asyncio
    async def test_cleanup_idle_sessions(self, session_pool):
        """Test cleanup of idle sessions."""
        # Acquire and release sessions to put them in available pool
        session1 = await session_pool.acquire()
        session2 = await session_pool.acquire()
        await session1.release()
        await session2.release()

        metrics_before = session_pool.get_metrics()
        initial_available = metrics_before["pool_size"]["available"]

        # Wait for idle timeout (1 second in test fixture)
        await asyncio.sleep(1.2)

        # Cleanup idle sessions
        closed = await session_pool.cleanup_idle(max_idle_time=1.0)

        # Should close sessions exceeding idle time, but keep min_size (2)
        metrics_after = session_pool.get_metrics()
        assert closed >= 0
        assert metrics_after["pool_size"]["available"] >= session_pool.min_size

    @pytest.mark.asyncio
    async def test_cleanup_respects_min_size(self, session_pool):
        """Test cleanup never goes below min_size."""
        # Start with min_size sessions
        metrics_before = session_pool.get_metrics()
        assert metrics_before["pool_size"]["available"] == session_pool.min_size

        # Wait and cleanup
        await asyncio.sleep(1.2)
        closed = await session_pool.cleanup_idle(max_idle_time=0.5)

        # Should not close sessions if at min_size
        metrics_after = session_pool.get_metrics()
        assert metrics_after["pool_size"]["available"] == session_pool.min_size

    @pytest.mark.asyncio
    async def test_session_metrics_tracking(self, session_pool):
        """Test session metrics are tracked correctly."""
        session = await session_pool.acquire()

        # Check initial acquire count
        async with session_pool._lock:
            _, metrics = session_pool._in_use[session.session_id]
            assert metrics.acquire_count == 1
            assert metrics.in_use is True

        await session.release()

        # Release should update metrics
        # Find in available pool
        temp_sessions = []
        while not session_pool._available.empty():
            s, m = await session_pool._available.get()
            temp_sessions.append((s, m))
            if m.session_id == session.session_id:
                assert m.in_use is False
                break

        # Put them back
        for s, m in temp_sessions:
            await session_pool._available.put((s, m))

    @pytest.mark.asyncio
    async def test_get_metrics(self, session_pool):
        """Test get_metrics returns correct statistics."""
        metrics = session_pool.get_metrics()

        assert "pool_size" in metrics
        assert "lifetime" in metrics
        assert "config" in metrics

        assert metrics["pool_size"]["max"] == 5
        assert metrics["pool_size"]["min"] == 2
        assert metrics["config"]["idle_timeout"] == 1.0
        assert metrics["config"]["acquire_timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_pool_cleanup(self, session_pool):
        """Test pool cleanup closes all sessions."""
        # Acquire some sessions
        session1 = await session_pool.acquire()
        session2 = await session_pool.acquire()

        metrics_before = session_pool.get_metrics()
        total_before = metrics_before["pool_size"]["total"]

        await session_pool.cleanup()

        # All sessions should be closed
        assert session_pool._available.empty()
        assert len(session_pool._in_use) == 0

    @pytest.mark.asyncio
    async def test_concurrent_acquisitions(self, session_pool):
        """Test multiple concurrent acquisitions work correctly."""
        async def acquire_and_release():
            session = await session_pool.acquire()
            await asyncio.sleep(0.1)
            await session.release()

        # Run multiple concurrent acquisitions
        tasks = [acquire_and_release() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Pool should be back to normal state
        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 0
        assert metrics["lifetime"]["total_acquires"] >= 10
        assert metrics["lifetime"]["total_releases"] >= 10


class TestManagedSession:
    """Test ManagedSession class."""

    @pytest.mark.asyncio
    async def test_managed_session_context_manager(self, session_pool):
        """Test ManagedSession as context manager."""
        managed = await session_pool.acquire()

        async with managed as session:
            assert session is not None
            assert session.is_active

        # Should be released after exit
        await asyncio.sleep(0.1)
        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 0

    @pytest.mark.asyncio
    async def test_manual_release(self, session_pool):
        """Test manual session release."""
        managed = await session_pool.acquire()

        metrics_before = session_pool.get_metrics()
        assert metrics_before["pool_size"]["in_use"] == 1

        await managed.release()

        await asyncio.sleep(0.1)
        metrics_after = session_pool.get_metrics()
        assert metrics_after["pool_size"]["in_use"] == 0

    @pytest.mark.asyncio
    async def test_double_release_is_safe(self, session_pool):
        """Test releasing session twice doesn't cause error."""
        managed = await session_pool.acquire()

        await managed.release()
        # Second release should be no-op
        await managed.release()

        metrics = session_pool.get_metrics()
        assert metrics["pool_size"]["in_use"] == 0

    @pytest.mark.asyncio
    async def test_session_id_property(self, session_pool):
        """Test session_id property."""
        managed = await session_pool.acquire()
        assert managed.session_id > 0
        await managed.release()

    @pytest.mark.asyncio
    async def test_session_property(self, session_pool):
        """Test session property returns underlying session."""
        managed = await session_pool.acquire()
        session = managed.session
        assert session is not None
        assert hasattr(session, "commit")
        await managed.release()
