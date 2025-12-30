"""
Tests pentru LiveTracker class.

Testează inițializare, setup cu handlers, collect logic, periodic refresh, WebSocket handling.
"""

import pytest
import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.collectors.live_tracker import LiveTracker, create_live_tracker
from src.browser.manager import BrowserManager


@pytest.fixture
def mock_browser_manager():
    """Mock pentru BrowserManager."""
    manager = AsyncMock(spec=BrowserManager)
    manager.new_page = AsyncMock()
    return manager


@pytest.fixture
def live_tracker(mock_browser_manager):
    """Fixture pentru LiveTracker instance."""
    return LiveTracker(mock_browser_manager, sport="football")


@pytest.fixture
def mock_http_interceptor():
    """Mock pentru HTTP interceptor."""
    interceptor = MagicMock()
    interceptor.on = MagicMock()
    interceptor.clear_handlers = MagicMock()
    return interceptor


@pytest.fixture
def mock_ws_interceptor():
    """Mock pentru WebSocket interceptor."""
    interceptor = MagicMock()
    interceptor.on_message = MagicMock()
    interceptor.on_score_update = MagicMock()
    interceptor.on_incident = MagicMock()
    interceptor.clear_handlers = MagicMock()
    interceptor.active_connections = 0
    return interceptor


class TestLiveTrackerInit:
    """Teste pentru inițializarea LiveTracker."""

    def test_init_with_valid_sport(self, mock_browser_manager):
        """Test inițializare cu sport valid."""
        tracker = LiveTracker(mock_browser_manager, sport="football")

        assert tracker.browser_manager == mock_browser_manager
        assert tracker.sport == "football"
        assert tracker.context_name == "live_football"
        assert tracker.url == "https://www.sofascore.com/football/livescore"
        assert tracker.on_live_data is None
        assert tracker.on_score_update is None
        assert tracker.on_incident is None
        assert tracker._refresh_task is None

    def test_init_with_different_sport(self, mock_browser_manager):
        """Test inițializare cu sport diferit."""
        tracker = LiveTracker(mock_browser_manager, sport="tennis")

        assert tracker.sport == "tennis"
        assert tracker.context_name == "live_tennis"
        assert tracker.url == "https://www.sofascore.com/tennis/livescore"

    def test_init_with_callbacks(self, mock_browser_manager):
        """Test inițializare cu callbacks."""
        on_live = AsyncMock()
        on_score = AsyncMock()
        on_inc = AsyncMock()

        tracker = LiveTracker(
            mock_browser_manager,
            sport="basketball",
            on_live_data=on_live,
            on_score_update=on_score,
            on_incident=on_inc
        )

        assert tracker.on_live_data == on_live
        assert tracker.on_score_update == on_score
        assert tracker.on_incident == on_inc

    def test_init_with_invalid_sport_raises(self, mock_browser_manager):
        """Test că inițializarea cu sport invalid aruncă ValueError."""
        with pytest.raises(ValueError, match="Unsupported sport"):
            LiveTracker(mock_browser_manager, sport="invalid_sport")

    def test_supported_sports(self):
        """Test că toate sporturile suportate au URL-uri."""
        expected_sports = ["football", "tennis", "basketball", "handball", "volleyball"]

        for sport in expected_sports:
            assert sport in LiveTracker.LIVE_URLS
            assert LiveTracker.LIVE_URLS[sport].startswith("https://www.sofascore.com/")


class TestLiveTrackerSetup:
    """Teste pentru setup()."""

    @pytest.mark.asyncio
    async def test_setup_calls_parent_setup(self, live_tracker, mock_browser_manager):
        """Test că setup() apelează setup() din clasa părinte."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                await live_tracker.setup()

                # Verifică că new_page a fost apelat (din parent setup)
                mock_browser_manager.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_registers_http_handler(self, live_tracker, mock_browser_manager):
        """Test că setup() înregistrează handler pentru HTTP responses."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page
        mock_http_interceptor = MagicMock()
        mock_http_interceptor.on = MagicMock()

        on_live_data = AsyncMock()
        live_tracker.on_live_data = on_live_data

        with patch('src.collectors.base.create_interceptor', new=AsyncMock(return_value=mock_http_interceptor)):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                await live_tracker.setup()

                # Verifică că handler-ul HTTP a fost înregistrat
                mock_http_interceptor.on.assert_called_once_with(
                    "live",
                    live_tracker._handle_live_response
                )

    @pytest.mark.asyncio
    async def test_setup_registers_ws_handlers(self, live_tracker, mock_browser_manager):
        """Test că setup() înregistrează handlers pentru WebSocket."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page
        mock_ws_interceptor = MagicMock()
        mock_ws_interceptor.on_score_update = MagicMock()
        mock_ws_interceptor.on_incident = MagicMock()

        on_score = AsyncMock()
        on_inc = AsyncMock()
        live_tracker.on_score_update = on_score
        live_tracker.on_incident = on_inc

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock(return_value=mock_ws_interceptor)):
                await live_tracker.setup()

                # Verifică că handlers WS au fost înregistrați
                mock_ws_interceptor.on_score_update.assert_called_once_with(on_score)
                mock_ws_interceptor.on_incident.assert_called_once_with(on_inc)

    @pytest.mark.asyncio
    async def test_setup_with_generic_ws_interceptor(self, live_tracker, mock_browser_manager):
        """Test setup cu WS interceptor generic (fără on_score_update)."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page
        mock_ws_interceptor = MagicMock()
        # Nu are on_score_update (interceptor generic)
        delattr(mock_ws_interceptor, 'on_score_update') if hasattr(mock_ws_interceptor, 'on_score_update') else None
        mock_ws_interceptor.on_message = MagicMock()

        on_score = AsyncMock()
        live_tracker.on_score_update = on_score

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock(return_value=mock_ws_interceptor)):
                await live_tracker.setup()

                # Verifică că fallback pe on_message a fost folosit
                mock_ws_interceptor.on_message.assert_called_once_with(live_tracker._handle_ws_message)


class TestLiveTrackerCollect:
    """Teste pentru collect()."""

    @pytest.mark.asyncio
    async def test_collect_navigates_to_live_page(self, live_tracker):
        """Test că collect() navighează la pagina live."""
        with patch.object(live_tracker, 'navigate_with_delay', new=AsyncMock()) as mock_nav:
            with patch.object(live_tracker, 'wait_for_data', new=AsyncMock()):
                # Oprește după prima iterație
                async def stop_after_short_time():
                    await asyncio.sleep(0.05)
                    live_tracker._running = False

                task = asyncio.create_task(stop_after_short_time())

                try:
                    await live_tracker.collect()
                except asyncio.CancelledError:
                    pass

                await task

                # Verifică că navigate a fost apelat cu URL-ul corect
                mock_nav.assert_called_once_with(
                    "https://www.sofascore.com/football/livescore",
                    wait_until="networkidle"
                )

    @pytest.mark.asyncio
    async def test_collect_waits_for_initial_data(self, live_tracker):
        """Test că collect() așteaptă date inițiale."""
        with patch.object(live_tracker, 'navigate_with_delay', new=AsyncMock()):
            with patch.object(live_tracker, 'wait_for_data', new=AsyncMock()) as mock_wait:
                async def stop_after_short_time():
                    await asyncio.sleep(0.05)
                    live_tracker._running = False

                task = asyncio.create_task(stop_after_short_time())

                try:
                    await live_tracker.collect()
                except asyncio.CancelledError:
                    pass

                await task

                # Verifică că wait_for_data a fost apelat
                mock_wait.assert_called_once_with(timeout=5.0)

    @pytest.mark.asyncio
    async def test_collect_starts_periodic_refresh(self, live_tracker):
        """Test că collect() pornește refresh periodic."""
        with patch.object(live_tracker, 'navigate_with_delay', new=AsyncMock()):
            with patch.object(live_tracker, 'wait_for_data', new=AsyncMock()):
                with patch.object(live_tracker, '_periodic_refresh', new=AsyncMock()) as mock_refresh:
                    live_tracker._running = True

                    # Start collect în background
                    collect_task = asyncio.create_task(live_tracker.collect())
                    await asyncio.sleep(0.1)

                    # Oprește
                    live_tracker._running = False
                    try:
                        await collect_task
                    except asyncio.CancelledError:
                        pass

                    # Verifică că _periodic_refresh a fost pornit
                    # (task-ul ar fi trebuit creat)
                    assert live_tracker._refresh_task is not None


class TestLiveTrackerPeriodicRefresh:
    """Teste pentru _periodic_refresh()."""

    @pytest.mark.asyncio
    async def test_periodic_refresh_reloads_page(self, live_tracker):
        """Test că _periodic_refresh() reîncarcă pagina."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_page.reload = AsyncMock()
        live_tracker.page = mock_page
        live_tracker._running = True

        # Folosește interval foarte mic pentru test
        with patch('src.config.settings.page_refresh_interval', 0.1):
            refresh_task = asyncio.create_task(live_tracker._periodic_refresh())

            # Așteaptă puțin pentru cel puțin un refresh
            await asyncio.sleep(0.15)

            # Oprește
            live_tracker._running = False
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass

            # Verifică că reload a fost apelat
            assert mock_page.reload.called

    @pytest.mark.asyncio
    async def test_periodic_refresh_stops_on_closed_page(self, live_tracker):
        """Test că _periodic_refresh() se oprește dacă pagina e închisă."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = True
        live_tracker.page = mock_page
        live_tracker._running = True

        with patch('src.config.settings.page_refresh_interval', 0.05):
            refresh_task = asyncio.create_task(live_tracker._periodic_refresh())

            await asyncio.sleep(0.1)

            # Task-ul ar trebui să se fi oprit singur
            assert refresh_task.done()

    @pytest.mark.asyncio
    async def test_periodic_refresh_continues_on_error(self, live_tracker):
        """Test că _periodic_refresh() continuă chiar dacă reload aruncă eroare."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        reload_count = 0

        async def reload_with_error(*args, **kwargs):
            nonlocal reload_count
            reload_count += 1
            if reload_count == 1:
                raise Exception("Reload failed")

        mock_page.reload = reload_with_error
        live_tracker.page = mock_page
        live_tracker._running = True

        with patch('src.config.settings.page_refresh_interval', 0.05):
            refresh_task = asyncio.create_task(live_tracker._periodic_refresh())

            # Așteaptă pentru mai multe încercări
            await asyncio.sleep(0.15)

            live_tracker._running = False
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass

            # Verifică că reload a fost încercat de mai multe ori (continuă după eroare)
            assert reload_count >= 2


class TestLiveTrackerHandlers:
    """Teste pentru handlers de date."""

    @pytest.mark.asyncio
    async def test_handle_live_response_calls_callback(self, live_tracker):
        """Test că _handle_live_response() apelează callback-ul utilizatorului."""
        on_live_data = AsyncMock()
        live_tracker.on_live_data = on_live_data

        data = {"events": [{"id": 1}, {"id": 2}]}
        match = re.match(r'/api/v1/sport/(\w+)/events/live', '/api/v1/sport/football/events/live')

        await live_tracker._handle_live_response(data, match)

        on_live_data.assert_called_once_with(data, match)

    @pytest.mark.asyncio
    async def test_handle_live_response_ignores_different_sport(self, live_tracker):
        """Test că _handle_live_response() ignoră date pentru alt sport."""
        on_live_data = AsyncMock()
        live_tracker.on_live_data = on_live_data

        data = {"events": [{"id": 1}]}
        match = re.match(r'/api/v1/sport/(\w+)/events/live', '/api/v1/sport/tennis/events/live')

        await live_tracker._handle_live_response(data, match)

        # Callback-ul NU ar trebui apelat pentru alt sport
        on_live_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_live_response_handles_errors(self, live_tracker):
        """Test că _handle_live_response() gestionează erori în callback."""
        async def failing_callback(data, match):
            raise Exception("Callback failed")

        live_tracker.on_live_data = failing_callback

        data = {"events": []}
        match = re.match(r'/api/v1/sport/(\w+)/events/live', '/api/v1/sport/football/events/live')

        # Nu ar trebui să arunce excepție
        await live_tracker._handle_live_response(data, match)

    @pytest.mark.asyncio
    async def test_handle_ws_message_routes_score_update(self, live_tracker):
        """Test că _handle_ws_message() rutează update-uri de scor."""
        on_score = AsyncMock()
        live_tracker.on_score_update = on_score

        data = {"type": "scoreUpdate", "eventId": 123, "score": "2-1"}

        await live_tracker._handle_ws_message(data)

        on_score.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_handle_ws_message_routes_incident(self, live_tracker):
        """Test că _handle_ws_message() rutează incidente."""
        on_incident = AsyncMock()
        live_tracker.on_incident = on_incident

        data = {"type": "incident", "eventId": 123, "incidentType": "goal"}

        await live_tracker._handle_ws_message(data)

        on_incident.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_handle_ws_message_ignores_unknown_type(self, live_tracker):
        """Test că _handle_ws_message() ignoră tipuri necunoscute."""
        on_score = AsyncMock()
        on_incident = AsyncMock()
        live_tracker.on_score_update = on_score
        live_tracker.on_incident = on_incident

        data = {"type": "unknown", "data": "something"}

        await live_tracker._handle_ws_message(data)

        # Niciunul nu ar trebui apelat
        on_score.assert_not_called()
        on_incident.assert_not_called()


class TestLiveTrackerCleanup:
    """Teste pentru cleanup()."""

    @pytest.mark.asyncio
    async def test_cleanup_cancels_refresh_task(self, live_tracker):
        """Test că cleanup() anulează task-ul de refresh."""
        mock_refresh_task = AsyncMock()
        mock_refresh_task.done.return_value = False
        mock_refresh_task.cancel = MagicMock()
        live_tracker._refresh_task = mock_refresh_task

        with patch('src.collectors.base.BaseCollector.cleanup', new=AsyncMock()):
            await live_tracker.cleanup()

            mock_refresh_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_calls_parent_cleanup(self, live_tracker):
        """Test că cleanup() apelează cleanup() din părinte."""
        with patch('src.collectors.base.BaseCollector.cleanup', new=AsyncMock()) as mock_parent:
            await live_tracker.cleanup()

            mock_parent.assert_called_once()


class TestCreateLiveTracker:
    """Teste pentru funcția create_live_tracker()."""

    @pytest.mark.asyncio
    async def test_create_live_tracker_creates_and_starts(self, mock_browser_manager):
        """Test că create_live_tracker() creează și pornește tracker-ul."""
        on_live = AsyncMock()

        with patch.object(LiveTracker, 'start', new=AsyncMock()) as mock_start:
            tracker = await create_live_tracker(
                mock_browser_manager,
                sport="football",
                on_live_data=on_live
            )

            assert isinstance(tracker, LiveTracker)
            assert tracker.sport == "football"
            assert tracker.on_live_data == on_live
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_live_tracker_with_all_callbacks(self, mock_browser_manager):
        """Test create_live_tracker() cu toate callbacks."""
        on_live = AsyncMock()
        on_score = AsyncMock()
        on_inc = AsyncMock()

        with patch.object(LiveTracker, 'start', new=AsyncMock()):
            tracker = await create_live_tracker(
                mock_browser_manager,
                sport="tennis",
                on_live_data=on_live,
                on_score_update=on_score,
                on_incident=on_inc
            )

            assert tracker.on_live_data == on_live
            assert tracker.on_score_update == on_score
            assert tracker.on_incident == on_inc


class TestLiveTrackerIntegration:
    """Teste de integrare pentru workflow complet."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_mocks(self, mock_browser_manager):
        """Test lifecycle complet cu mock-uri."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_page.goto = AsyncMock()
        mock_page.reload = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        on_live_data = AsyncMock()
        tracker = LiveTracker(
            mock_browser_manager,
            sport="football",
            on_live_data=on_live_data
        )

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                with patch('asyncio.sleep', new=AsyncMock()):
                    with patch('src.config.settings.page_refresh_interval', 10):
                        # Start
                        await tracker.start()
                        await asyncio.sleep(0.05)

                        assert tracker.is_running() is True

                        # Stop
                        await tracker.stop()
                        assert tracker.is_running() is False
