"""Tests for CollectorCoordinator."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator.coordinator import CollectorCoordinator, create_coordinator


@pytest.mark.asyncio
class TestCollectorCoordinator:
    """Test cases for CollectorCoordinator."""

    @pytest.fixture
    async def coordinator(self):
        """Create a coordinator instance for testing."""
        with patch("src.orchestrator.coordinator.init_db"), \
             patch("src.orchestrator.coordinator.BrowserManager"):
            coordinator = CollectorCoordinator(headless=True)
            await coordinator.initialize()
            yield coordinator
            await coordinator.cleanup()

    async def test_initialization(self):
        """Test coordinator initialization."""
        with patch("src.orchestrator.coordinator.init_db") as mock_init_db, \
             patch("src.orchestrator.coordinator.BrowserManager") as mock_browser:

            coordinator = CollectorCoordinator(headless=True)
            assert coordinator.headless is True
            assert coordinator.browser_manager is None
            assert coordinator.handler is None
            assert len(coordinator.collectors) == 0
            assert coordinator._running is False

            await coordinator.initialize()

            mock_init_db.assert_called_once()
            assert coordinator.browser_manager is not None
            assert coordinator.handler is not None
            assert coordinator._running is True

            await coordinator.cleanup()

    async def test_create_coordinator(self):
        """Test create_coordinator convenience function."""
        with patch("src.orchestrator.coordinator.init_db"), \
             patch("src.orchestrator.coordinator.BrowserManager"):

            coordinator = await create_coordinator(headless=True, auto_init=True)

            assert coordinator is not None
            assert coordinator._running is True
            assert coordinator.browser_manager is not None

            await coordinator.cleanup()

    async def test_context_manager(self):
        """Test coordinator as async context manager."""
        with patch("src.orchestrator.coordinator.init_db"), \
             patch("src.orchestrator.coordinator.BrowserManager"):

            async with create_coordinator() as coordinator:
                assert coordinator._running is True
                assert coordinator.browser_manager is not None

            # After exit, should be cleaned up
            assert coordinator._running is False

    async def test_add_live_tracker(self, coordinator):
        """Test adding a live tracker."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.is_running.return_value = True
            mock_tracker_class.return_value = mock_tracker

            tracker = await coordinator.add_live_tracker("football", auto_start=True)

            assert "live_football" in coordinator.collectors
            assert coordinator.collectors["live_football"] == tracker
            mock_tracker.start.assert_called_once()

    async def test_add_live_tracker_no_auto_start(self, coordinator):
        """Test adding a live tracker without auto-start."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker_class.return_value = mock_tracker

            tracker = await coordinator.add_live_tracker("tennis", auto_start=False)

            assert "live_tennis" in coordinator.collectors
            mock_tracker.start.assert_not_called()

    async def test_add_duplicate_live_tracker(self, coordinator):
        """Test adding a duplicate live tracker returns existing one."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker_class.return_value = mock_tracker

            tracker1 = await coordinator.add_live_tracker("football")
            tracker2 = await coordinator.add_live_tracker("football")

            assert tracker1 == tracker2
            assert len(coordinator.collectors) == 1

    async def test_add_daily_collector(self, coordinator):
        """Test adding a daily events collector."""
        with patch("src.orchestrator.coordinator.DailyEventsCollector") as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector.is_running.return_value = True
            mock_collector_class.return_value = mock_collector

            start = date.today()
            end = date.today() + timedelta(days=7)

            collector = await coordinator.add_daily_collector(
                "basketball",
                start_date=start,
                end_date=end,
                auto_start=True
            )

            assert collector == mock_collector
            mock_collector.start.assert_called_once()

    async def test_add_live_trackers_for_all_sports(self, coordinator):
        """Test adding live trackers for all configured sports."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class, \
             patch("src.config.settings.sports", ["football", "tennis", "basketball"]):

            mock_tracker = AsyncMock()
            mock_tracker_class.return_value = mock_tracker

            trackers = await coordinator.add_live_trackers_for_all_sports()

            assert len(trackers) == 3
            assert len(coordinator.collectors) == 3
            assert "live_football" in coordinator.collectors
            assert "live_tennis" in coordinator.collectors
            assert "live_basketball" in coordinator.collectors

    async def test_backfill_historical_data(self, coordinator):
        """Test backfill historical data convenience method."""
        with patch("src.orchestrator.coordinator.DailyEventsCollector") as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector_class.return_value = mock_collector

            collector = await coordinator.backfill_historical_data("football", days_back=30)

            assert collector == mock_collector
            # Verify backfill_mode was set to True
            call_kwargs = mock_collector_class.call_args[1]
            assert call_kwargs.get("backfill_mode") is True

    async def test_collect_upcoming_matches(self, coordinator):
        """Test collect upcoming matches convenience method."""
        with patch("src.orchestrator.coordinator.DailyEventsCollector") as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector_class.return_value = mock_collector

            collector = await coordinator.collect_upcoming_matches("tennis", days_ahead=7)

            assert collector == mock_collector
            # Verify backfill_mode was set to False
            call_kwargs = mock_collector_class.call_args[1]
            assert call_kwargs.get("backfill_mode") is False

    async def test_stop_collector(self, coordinator):
        """Test stopping a specific collector."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker_class.return_value = mock_tracker

            await coordinator.add_live_tracker("football")
            await coordinator.stop_collector("live_football")

            mock_tracker.stop.assert_called_once()

    async def test_stop_nonexistent_collector(self, coordinator):
        """Test stopping a nonexistent collector doesn't raise error."""
        # Should not raise
        await coordinator.stop_collector("nonexistent")

    async def test_stop_all_collectors(self, coordinator):
        """Test stopping all collectors."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker1 = AsyncMock()
            mock_tracker1.is_running.return_value = True
            mock_tracker2 = AsyncMock()
            mock_tracker2.is_running.return_value = True

            mock_tracker_class.side_effect = [mock_tracker1, mock_tracker2]

            await coordinator.add_live_tracker("football")
            await coordinator.add_live_tracker("tennis")

            await coordinator.stop_all_collectors()

            mock_tracker1.stop.assert_called_once()
            mock_tracker2.stop.assert_called_once()

    async def test_get_status(self, coordinator):
        """Test getting coordinator status."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.is_running.return_value = True
            mock_tracker.sport = "football"
            mock_tracker_class.return_value = mock_tracker

            await coordinator.add_live_tracker("football")

            status = coordinator.get_status()

            assert status["coordinator_running"] is True
            assert status["browser_headless"] is True
            assert status["total_collectors"] == 1
            assert status["running_collectors"] == 1
            assert "live_football" in status["collectors"]
            assert status["collectors"]["live_football"]["type"] == "live"
            assert status["collectors"]["live_football"]["sport"] == "football"

    async def test_cleanup(self, coordinator):
        """Test coordinator cleanup."""
        with patch("src.orchestrator.coordinator.LiveTracker") as mock_tracker_class:
            mock_tracker = AsyncMock()
            mock_tracker.is_running.return_value = True
            mock_tracker_class.return_value = mock_tracker

            await coordinator.add_live_tracker("football")
            await coordinator.cleanup()

            mock_tracker.stop.assert_called_once()
            assert coordinator._running is False

    async def test_initialization_without_coordinator(self):
        """Test that methods fail before initialization."""
        coordinator = CollectorCoordinator()

        with pytest.raises(RuntimeError, match="Coordinator not initialized"):
            await coordinator.add_live_tracker("football")

        with pytest.raises(RuntimeError, match="Coordinator not initialized"):
            await coordinator.add_daily_collector("football")
