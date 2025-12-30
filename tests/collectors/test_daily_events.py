"""
Tests pentru DailyEventsCollector class.

Testează inițializare, validare date range, collect logic, progress tracking, backfill.
"""

import pytest
import asyncio
import re
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.collectors.daily_events import (
    DailyEventsCollector,
    create_daily_collector,
    backfill_historical_data
)
from src.browser.manager import BrowserManager


@pytest.fixture
def mock_browser_manager():
    """Mock pentru BrowserManager."""
    manager = AsyncMock(spec=BrowserManager)
    manager.new_page = AsyncMock()
    return manager


@pytest.fixture
def today():
    """Fixture pentru data de astăzi."""
    return date(2024, 12, 30)


@pytest.fixture
def daily_collector(mock_browser_manager, today):
    """Fixture pentru DailyEventsCollector instance."""
    return DailyEventsCollector(
        mock_browser_manager,
        sport="football",
        start_date=today,
        end_date=today + timedelta(days=2)
    )


class TestDailyEventsCollectorInit:
    """Teste pentru inițializarea DailyEventsCollector."""

    def test_init_with_date_range(self, mock_browser_manager, today):
        """Test inițializare cu range de date."""
        start = today
        end = today + timedelta(days=5)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="football",
            start_date=start,
            end_date=end
        )

        assert collector.browser_manager == mock_browser_manager
        assert collector.sport == "football"
        assert collector.context_name == "daily_football"
        assert collector.start_date == start
        assert collector.end_date == end
        assert collector.total_days == 6  # 5 days + 1
        assert collector.processed_days == 0
        assert collector.backfill_mode is False

    def test_init_defaults_to_today(self, mock_browser_manager):
        """Test că start_date default este astăzi."""
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="tennis"
        )

        assert collector.start_date == date.today()
        assert collector.end_date == date.today()
        assert collector.total_days == 1

    def test_init_with_callback(self, mock_browser_manager, today):
        """Test inițializare cu callback."""
        on_scheduled = AsyncMock()

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="basketball",
            start_date=today,
            on_scheduled_data=on_scheduled
        )

        assert collector.on_scheduled_data == on_scheduled

    def test_init_with_backfill_mode(self, mock_browser_manager, today):
        """Test inițializare cu backfill mode activat."""
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="handball",
            start_date=today,
            backfill_mode=True
        )

        assert collector.backfill_mode is True

    def test_init_validates_date_range(self, mock_browser_manager, today):
        """Test că validarea aruncă excepție dacă end_date < start_date."""
        start = today
        end = today - timedelta(days=5)

        with pytest.raises(ValueError, match="cannot be before"):
            DailyEventsCollector(
                mock_browser_manager,
                sport="football",
                start_date=start,
                end_date=end
            )

    def test_init_single_day_range(self, mock_browser_manager, today):
        """Test cu un singur day (start == end)."""
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="volleyball",
            start_date=today,
            end_date=today
        )

        assert collector.total_days == 1
        assert collector.start_date == collector.end_date


class TestDailyEventsCollectorSetup:
    """Teste pentru setup()."""

    @pytest.mark.asyncio
    async def test_setup_calls_parent_setup(self, daily_collector, mock_browser_manager):
        """Test că setup() apelează setup() din clasa părinte."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                await daily_collector.setup()

                # Verifică că new_page a fost apelat (din parent setup)
                mock_browser_manager.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_registers_http_handler(self, daily_collector, mock_browser_manager):
        """Test că setup() înregistrează handler pentru HTTP responses."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page
        mock_http_interceptor = MagicMock()
        mock_http_interceptor.on = MagicMock()

        on_scheduled_data = AsyncMock()
        daily_collector.on_scheduled_data = on_scheduled_data

        with patch('src.collectors.base.create_interceptor', new=AsyncMock(return_value=mock_http_interceptor)):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                await daily_collector.setup()

                # Verifică că handler-ul HTTP a fost înregistrat
                mock_http_interceptor.on.assert_called_once_with(
                    "scheduled",
                    daily_collector._handle_scheduled_response
                )


class TestDailyEventsCollectorCollect:
    """Teste pentru collect()."""

    @pytest.mark.asyncio
    async def test_collect_iterates_through_dates(self, mock_browser_manager, today):
        """Test că collect() iterează prin toate datele."""
        start = today
        end = today + timedelta(days=2)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="football",
            start_date=start,
            end_date=end
        )

        with patch.object(collector, '_collect_date', new=AsyncMock()) as mock_collect_date:
            with patch.object(collector, 'setup', new=AsyncMock()):
                collector._running = True
                await collector.collect()

                # Verifică că _collect_date a fost apelat pentru fiecare dată
                assert mock_collect_date.call_count == 3
                mock_collect_date.assert_any_call(start)
                mock_collect_date.assert_any_call(start + timedelta(days=1))
                mock_collect_date.assert_any_call(start + timedelta(days=2))

    @pytest.mark.asyncio
    async def test_collect_updates_progress(self, mock_browser_manager, today):
        """Test că collect() actualizează progresul."""
        start = today
        end = today + timedelta(days=1)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="tennis",
            start_date=start,
            end_date=end
        )

        with patch.object(collector, '_collect_date', new=AsyncMock()):
            with patch.object(collector, 'setup', new=AsyncMock()):
                collector._running = True
                await collector.collect()

                assert collector.processed_days == 2

    @pytest.mark.asyncio
    async def test_collect_applies_backfill_delay(self, mock_browser_manager, today):
        """Test că collect() aplică delay în backfill mode."""
        start = today
        end = today + timedelta(days=1)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="basketball",
            start_date=start,
            end_date=end,
            backfill_mode=True
        )

        with patch.object(collector, '_collect_date', new=AsyncMock()):
            with patch.object(collector, 'setup', new=AsyncMock()):
                with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
                    with patch('src.config.settings.backfill_delay', 2.0):
                        collector._running = True
                        await collector.collect()

                        # Verifică că sleep a fost apelat cu backfill delay
                        mock_sleep.assert_any_call(2.0)

    @pytest.mark.asyncio
    async def test_collect_no_delay_without_backfill(self, mock_browser_manager, today):
        """Test că collect() nu aplică delay fără backfill mode."""
        start = today
        end = today + timedelta(days=1)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="handball",
            start_date=start,
            end_date=end,
            backfill_mode=False
        )

        with patch.object(collector, '_collect_date', new=AsyncMock()):
            with patch.object(collector, 'setup', new=AsyncMock()):
                with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
                    collector._running = True
                    await collector.collect()

                    # Nu ar trebui să existe apeluri sleep pentru backfill delay
                    # (poate exista pentru wait_for_data, dar nu pentru backfill)
                    assert mock_sleep.call_count == 0

    @pytest.mark.asyncio
    async def test_collect_continues_on_error(self, mock_browser_manager, today):
        """Test că collect() continuă la următoarea dată dacă apare eroare."""
        start = today
        end = today + timedelta(days=2)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="volleyball",
            start_date=start,
            end_date=end
        )

        call_count = 0

        async def collect_with_error(target_date):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Collection failed for middle date")

        with patch.object(collector, '_collect_date', new=collect_with_error):
            with patch.object(collector, 'setup', new=AsyncMock()):
                collector._running = True
                await collector.collect()

                # Verifică că toate cele 3 date au fost încercate
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_collect_stops_running_after_completion(self, mock_browser_manager, today):
        """Test că collect() setează _running = False după finalizare."""
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="football",
            start_date=today,
            end_date=today
        )

        with patch.object(collector, '_collect_date', new=AsyncMock()):
            with patch.object(collector, 'setup', new=AsyncMock()):
                collector._running = True
                await collector.collect()

                assert collector._running is False


class TestDailyEventsCollectorCollectDate:
    """Teste pentru _collect_date()."""

    @pytest.mark.asyncio
    async def test_collect_date_navigates_to_url(self, daily_collector, today):
        """Test că _collect_date() navighează la URL-ul corect."""
        with patch.object(daily_collector, 'navigate_with_delay', new=AsyncMock()) as mock_nav:
            with patch.object(daily_collector, 'wait_for_data', new=AsyncMock()):
                await daily_collector._collect_date(today)

                expected_url = f"https://www.sofascore.com/football/{today.strftime('%Y-%m-%d')}"
                mock_nav.assert_called_once_with(expected_url, wait_until="networkidle")

    @pytest.mark.asyncio
    async def test_collect_date_waits_for_data(self, daily_collector, today):
        """Test că _collect_date() așteaptă interceptarea datelor."""
        with patch.object(daily_collector, 'navigate_with_delay', new=AsyncMock()):
            with patch.object(daily_collector, 'wait_for_data', new=AsyncMock()) as mock_wait:
                await daily_collector._collect_date(today)

                mock_wait.assert_called_once_with(timeout=5.0)

    @pytest.mark.asyncio
    async def test_collect_date_formats_date_correctly(self, daily_collector):
        """Test că _collect_date() formatează corect data în URL."""
        test_date = date(2024, 1, 5)

        with patch.object(daily_collector, 'navigate_with_delay', new=AsyncMock()) as mock_nav:
            with patch.object(daily_collector, 'wait_for_data', new=AsyncMock()):
                await daily_collector._collect_date(test_date)

                expected_url = "https://www.sofascore.com/football/2024-01-05"
                mock_nav.assert_called_once_with(expected_url, wait_until="networkidle")


class TestDailyEventsCollectorHandlers:
    """Teste pentru handlers de date."""

    @pytest.mark.asyncio
    async def test_handle_scheduled_response_calls_callback(self, daily_collector):
        """Test că _handle_scheduled_response() apelează callback-ul."""
        on_scheduled = AsyncMock()
        daily_collector.on_scheduled_data = on_scheduled

        data = {"events": [{"id": 1}, {"id": 2}]}
        match = re.match(
            r'/api/v1/sport/(\w+)/scheduled-events/(\d{4}-\d{2}-\d{2})',
            '/api/v1/sport/football/scheduled-events/2024-12-30'
        )

        await daily_collector._handle_scheduled_response(data, match)

        on_scheduled.assert_called_once_with(data, match)

    @pytest.mark.asyncio
    async def test_handle_scheduled_response_ignores_different_sport(self, daily_collector):
        """Test că _handle_scheduled_response() ignoră date pentru alt sport."""
        on_scheduled = AsyncMock()
        daily_collector.on_scheduled_data = on_scheduled

        data = {"events": [{"id": 1}]}
        match = re.match(
            r'/api/v1/sport/(\w+)/scheduled-events/(\d{4}-\d{2}-\d{2})',
            '/api/v1/sport/tennis/scheduled-events/2024-12-30'
        )

        await daily_collector._handle_scheduled_response(data, match)

        # Callback-ul NU ar trebui apelat pentru alt sport
        on_scheduled.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_scheduled_response_handles_errors(self, daily_collector):
        """Test că _handle_scheduled_response() gestionează erori în callback."""
        async def failing_callback(data, match):
            raise Exception("Callback failed")

        daily_collector.on_scheduled_data = failing_callback

        data = {"events": []}
        match = re.match(
            r'/api/v1/sport/(\w+)/scheduled-events/(\d{4}-\d{2}-\d{2})',
            '/api/v1/sport/football/scheduled-events/2024-12-30'
        )

        # Nu ar trebui să arunce excepție
        await daily_collector._handle_scheduled_response(data, match)


class TestDailyEventsCollectorProgress:
    """Teste pentru tracking progres."""

    def test_get_progress_returns_correct_info(self, mock_browser_manager, today):
        """Test că get_progress() returnează informații corecte."""
        start = today
        end = today + timedelta(days=4)

        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="football",
            start_date=start,
            end_date=end
        )

        collector.processed_days = 3

        progress = collector.get_progress()

        assert progress["sport"] == "football"
        assert progress["start_date"] == start.isoformat()
        assert progress["end_date"] == end.isoformat()
        assert progress["total_days"] == 5
        assert progress["processed_days"] == 3
        assert progress["progress_percent"] == 60.0
        assert progress["is_running"] is False

    def test_get_progress_zero_days(self, mock_browser_manager, today):
        """Test get_progress() când nu s-au procesat zile."""
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="tennis",
            start_date=today,
            end_date=today
        )

        progress = collector.get_progress()

        assert progress["processed_days"] == 0
        assert progress["progress_percent"] == 0.0


class TestCreateDailyCollector:
    """Teste pentru funcția create_daily_collector()."""

    @pytest.mark.asyncio
    async def test_create_daily_collector_creates_and_starts(self, mock_browser_manager, today):
        """Test că create_daily_collector() creează și pornește collector-ul."""
        on_scheduled = AsyncMock()

        with patch.object(DailyEventsCollector, 'start', new=AsyncMock()) as mock_start:
            collector = await create_daily_collector(
                mock_browser_manager,
                sport="football",
                start_date=today,
                on_scheduled_data=on_scheduled,
                auto_start=True
            )

            assert isinstance(collector, DailyEventsCollector)
            assert collector.sport == "football"
            assert collector.start_date == today
            assert collector.on_scheduled_data == on_scheduled
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_daily_collector_no_auto_start(self, mock_browser_manager, today):
        """Test create_daily_collector() cu auto_start=False."""
        with patch.object(DailyEventsCollector, 'start', new=AsyncMock()) as mock_start:
            collector = await create_daily_collector(
                mock_browser_manager,
                sport="tennis",
                start_date=today,
                auto_start=False
            )

            # Start nu ar trebui să fie apelat
            mock_start.assert_not_called()
            assert isinstance(collector, DailyEventsCollector)

    @pytest.mark.asyncio
    async def test_create_daily_collector_with_backfill(self, mock_browser_manager, today):
        """Test create_daily_collector() cu backfill mode."""
        collector = await create_daily_collector(
            mock_browser_manager,
            sport="basketball",
            start_date=today,
            backfill_mode=True,
            auto_start=False
        )

        assert collector.backfill_mode is True


class TestBackfillHistoricalData:
    """Teste pentru funcția backfill_historical_data()."""

    @pytest.mark.asyncio
    async def test_backfill_calculates_date_range(self, mock_browser_manager):
        """Test că backfill_historical_data() calculează corect range-ul de date."""
        with patch.object(DailyEventsCollector, 'start', new=AsyncMock()):
            with patch('src.collectors.daily_events.date') as mock_date:
                mock_today = date(2024, 12, 30)
                mock_date.today.return_value = mock_today

                collector = await backfill_historical_data(
                    mock_browser_manager,
                    sport="football",
                    days_back=30
                )

                expected_start = mock_today - timedelta(days=30)
                expected_end = mock_today

                assert collector.start_date == expected_start
                assert collector.end_date == expected_end
                assert collector.backfill_mode is True

    @pytest.mark.asyncio
    async def test_backfill_with_callback(self, mock_browser_manager):
        """Test backfill_historical_data() cu callback."""
        on_scheduled = AsyncMock()

        with patch.object(DailyEventsCollector, 'start', new=AsyncMock()):
            collector = await backfill_historical_data(
                mock_browser_manager,
                sport="tennis",
                days_back=7,
                on_scheduled_data=on_scheduled
            )

            assert collector.on_scheduled_data == on_scheduled

    @pytest.mark.asyncio
    async def test_backfill_auto_starts(self, mock_browser_manager):
        """Test că backfill_historical_data() pornește automat collector-ul."""
        with patch.object(DailyEventsCollector, 'start', new=AsyncMock()) as mock_start:
            await backfill_historical_data(
                mock_browser_manager,
                sport="handball",
                days_back=14
            )

            mock_start.assert_called_once()


class TestDailyEventsCollectorIntegration:
    """Teste de integrare pentru workflow complet."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_single_day(self, mock_browser_manager, today):
        """Test lifecycle complet pentru o singură zi."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_page.goto = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        on_scheduled = AsyncMock()
        collector = DailyEventsCollector(
            mock_browser_manager,
            sport="volleyball",
            start_date=today,
            end_date=today,
            on_scheduled_data=on_scheduled
        )

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                with patch('asyncio.sleep', new=AsyncMock()):
                    # Start
                    await collector.start()
                    await asyncio.sleep(0.1)

                    # Verifică că rulează
                    # (s-ar putea să se fi terminat deja pentru o singură zi)

                    # Așteaptă finalizare
                    max_wait = 1.0
                    start_time = asyncio.get_event_loop().time()
                    while collector.is_running():
                        await asyncio.sleep(0.05)
                        if asyncio.get_event_loop().time() - start_time > max_wait:
                            break

                    # Stop
                    await collector.stop()

                    # Verifică că s-a terminat
                    assert collector.processed_days == 1
                    assert collector.is_running() is False
