"""
Tests pentru BaseCollector abstract class.

Testează inițializare, start/stop, setup/cleanup, navigate_with_delay, error handling.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.collectors.base import BaseCollector
from src.browser.manager import BrowserManager


# Concrete implementation pentru testare (BaseCollector este abstract)
class ConcreteCollector(BaseCollector):
    """Implementare concretă pentru testare."""

    def __init__(self, browser_manager, sport=None, context_name=None):
        super().__init__(browser_manager, sport, context_name)
        self.collect_called = False
        self.collect_count = 0

    async def collect(self):
        """Implementare simplă pentru testare."""
        self.collect_called = True
        self.collect_count += 1
        await asyncio.sleep(0.1)


@pytest.fixture
def mock_browser_manager():
    """Mock pentru BrowserManager."""
    manager = AsyncMock(spec=BrowserManager)
    manager.new_page = AsyncMock()
    return manager


@pytest.fixture
def concrete_collector(mock_browser_manager):
    """Fixture pentru ConcreteCollector instance."""
    return ConcreteCollector(mock_browser_manager, sport="football")


@pytest.fixture
def concrete_collector_no_sport(mock_browser_manager):
    """Fixture pentru ConcreteCollector fără sport specificat."""
    return ConcreteCollector(mock_browser_manager)


class TestBaseCollectorInit:
    """Teste pentru inițializarea BaseCollector."""

    def test_init_with_sport(self, mock_browser_manager):
        """Test inițializare cu sport specificat."""
        collector = ConcreteCollector(mock_browser_manager, sport="football")

        assert collector.browser_manager == mock_browser_manager
        assert collector.sport == "football"
        assert collector.context_name == "football"
        assert collector.page is None
        assert collector.http_interceptor is None
        assert collector.ws_interceptor is None
        assert collector._running is False
        assert collector._task is None

    def test_init_with_custom_context_name(self, mock_browser_manager):
        """Test inițializare cu context_name custom."""
        collector = ConcreteCollector(
            mock_browser_manager,
            sport="tennis",
            context_name="custom_context"
        )

        assert collector.sport == "tennis"
        assert collector.context_name == "custom_context"

    def test_init_without_sport(self, mock_browser_manager):
        """Test inițializare fără sport."""
        collector = ConcreteCollector(mock_browser_manager)

        assert collector.sport is None
        assert collector.context_name == "default"

    def test_init_with_context_name_no_sport(self, mock_browser_manager):
        """Test inițializare cu context_name dar fără sport."""
        collector = ConcreteCollector(
            mock_browser_manager,
            context_name="my_context"
        )

        assert collector.sport is None
        assert collector.context_name == "my_context"


class TestBaseCollectorStartStop:
    """Teste pentru start() și stop()."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, concrete_collector):
        """Test că start() setează flag-ul _running."""
        await concrete_collector.start()

        assert concrete_collector._running is True
        assert concrete_collector._task is not None

        # Cleanup
        await concrete_collector.stop()

    @pytest.mark.asyncio
    async def test_start_already_running_warning(self, concrete_collector):
        """Test că start() pe un collector deja pornit nu face nimic."""
        await concrete_collector.start()

        # Start din nou
        task1 = concrete_collector._task
        await concrete_collector.start()
        task2 = concrete_collector._task

        # Verifică că task-ul rămâne același
        assert task1 == task2
        assert concrete_collector._running is True

        # Cleanup
        await concrete_collector.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_flag_false(self, concrete_collector):
        """Test că stop() setează _running la False."""
        await concrete_collector.start()
        await asyncio.sleep(0.05)  # Lasă să înceapă

        await concrete_collector.stop()

        assert concrete_collector._running is False

    @pytest.mark.asyncio
    async def test_stop_calls_cleanup(self, concrete_collector):
        """Test că stop() apelează cleanup()."""
        with patch.object(concrete_collector, 'cleanup', new=AsyncMock()) as mock_cleanup:
            await concrete_collector.start()
            await asyncio.sleep(0.05)

            await concrete_collector.stop()

            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_running_warning(self, concrete_collector):
        """Test că stop() pe un collector deja oprit nu face nimic."""
        assert concrete_collector._running is False

        # Stop pe collector care nu rulează
        await concrete_collector.stop()

        # Nu ar trebui să arunce excepție
        assert concrete_collector._running is False

    @pytest.mark.asyncio
    async def test_is_running_reflects_state(self, concrete_collector):
        """Test că is_running() reflectă starea curentă."""
        assert concrete_collector.is_running() is False

        await concrete_collector.start()
        assert concrete_collector.is_running() is True

        await concrete_collector.stop()
        assert concrete_collector.is_running() is False


class TestBaseCollectorSetup:
    """Teste pentru setup()."""

    @pytest.mark.asyncio
    async def test_setup_creates_page(self, concrete_collector, mock_browser_manager):
        """Test că setup() creează o pagină."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()) as mock_create_http:
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()) as mock_create_ws:
                mock_http_interceptor = AsyncMock()
                mock_ws_interceptor = AsyncMock()
                mock_create_http.return_value = mock_http_interceptor
                mock_create_ws.return_value = mock_ws_interceptor

                await concrete_collector.setup()

                # Verifică că pagina a fost creată
                mock_browser_manager.new_page.assert_called_once_with("football")
                assert concrete_collector.page == mock_page

    @pytest.mark.asyncio
    async def test_setup_creates_interceptors(self, concrete_collector, mock_browser_manager):
        """Test că setup() creează HTTP și WS interceptors."""
        mock_page = AsyncMock()
        mock_browser_manager.new_page.return_value = mock_page

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()) as mock_create_http:
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()) as mock_create_ws:
                mock_http_interceptor = AsyncMock()
                mock_ws_interceptor = AsyncMock()
                mock_create_http.return_value = mock_http_interceptor
                mock_create_ws.return_value = mock_ws_interceptor

                await concrete_collector.setup()

                # Verifică că interceptorii au fost creați
                mock_create_http.assert_called_once_with(mock_page)
                mock_create_ws.assert_called_once_with(mock_page)
                assert concrete_collector.http_interceptor == mock_http_interceptor
                assert concrete_collector.ws_interceptor == mock_ws_interceptor


class TestBaseCollectorCleanup:
    """Teste pentru cleanup()."""

    @pytest.mark.asyncio
    async def test_cleanup_clears_http_interceptor_handlers(self, concrete_collector):
        """Test că cleanup() curăță handler-ele HTTP interceptor."""
        mock_http_interceptor = MagicMock()
        mock_http_interceptor.clear_handlers = MagicMock()
        concrete_collector.http_interceptor = mock_http_interceptor

        await concrete_collector.cleanup()

        mock_http_interceptor.clear_handlers.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_clears_ws_interceptor_handlers(self, concrete_collector):
        """Test că cleanup() curăță handler-ele WS interceptor."""
        mock_ws_interceptor = MagicMock()
        mock_ws_interceptor.clear_handlers = MagicMock()
        concrete_collector.ws_interceptor = mock_ws_interceptor

        await concrete_collector.cleanup()

        mock_ws_interceptor.clear_handlers.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_closes_page(self, concrete_collector):
        """Test că cleanup() închide pagina."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_page.close = AsyncMock()
        concrete_collector.page = mock_page

        await concrete_collector.cleanup()

        mock_page.close.assert_called_once()
        assert concrete_collector.page is None

    @pytest.mark.asyncio
    async def test_cleanup_with_no_page(self, concrete_collector):
        """Test că cleanup() funcționează chiar dacă nu există pagină."""
        concrete_collector.page = None

        # Nu ar trebui să arunce excepție
        await concrete_collector.cleanup()

        assert concrete_collector.page is None

    @pytest.mark.asyncio
    async def test_cleanup_with_closed_page(self, concrete_collector):
        """Test că cleanup() nu încearcă să închidă o pagină deja închisă."""
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = True
        mock_page.close = AsyncMock()
        concrete_collector.page = mock_page

        await concrete_collector.cleanup()

        # close() nu ar trebui să fie apelat pentru pagini deja închise
        mock_page.close.assert_not_called()


class TestBaseCollectorNavigate:
    """Teste pentru navigate_with_delay()."""

    @pytest.mark.asyncio
    async def test_navigate_with_delay_navigates_to_url(self, concrete_collector):
        """Test că navigate_with_delay() navighează la URL."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        concrete_collector.page = mock_page

        with patch('asyncio.sleep', new=AsyncMock()):
            await concrete_collector.navigate_with_delay("https://www.sofascore.com")

            mock_page.goto.assert_called_once_with(
                "https://www.sofascore.com",
                wait_until="networkidle",
                timeout=60000
            )

    @pytest.mark.asyncio
    async def test_navigate_with_delay_uses_custom_wait_until(self, concrete_collector):
        """Test că navigate_with_delay() respectă parametrul wait_until."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        concrete_collector.page = mock_page

        with patch('asyncio.sleep', new=AsyncMock()):
            await concrete_collector.navigate_with_delay(
                "https://www.sofascore.com",
                wait_until="load"
            )

            mock_page.goto.assert_called_once_with(
                "https://www.sofascore.com",
                wait_until="load",
                timeout=60000
            )

    @pytest.mark.asyncio
    async def test_navigate_with_delay_adds_delay(self, concrete_collector):
        """Test că navigate_with_delay() adaugă un delay înainte de navigare."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        concrete_collector.page = mock_page

        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            await concrete_collector.navigate_with_delay("https://www.sofascore.com")

            # Verifică că sleep a fost apelat
            assert mock_sleep.called
            # Verifică că delay-ul este pozitiv
            delay = mock_sleep.call_args[0][0]
            assert delay > 0

    @pytest.mark.asyncio
    async def test_navigate_without_page_raises(self, concrete_collector):
        """Test că navigate_with_delay() aruncă excepție dacă pagina nu e inițializată."""
        concrete_collector.page = None

        with pytest.raises(RuntimeError, match="Page not initialized"):
            await concrete_collector.navigate_with_delay("https://www.sofascore.com")

    @pytest.mark.asyncio
    async def test_navigate_propagates_errors(self, concrete_collector):
        """Test că navigate_with_delay() propagă erorile de navigare."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))
        concrete_collector.page = mock_page

        with patch('asyncio.sleep', new=AsyncMock()):
            with pytest.raises(Exception, match="Navigation failed"):
                await concrete_collector.navigate_with_delay("https://www.sofascore.com")


class TestBaseCollectorWaitForData:
    """Teste pentru wait_for_data()."""

    @pytest.mark.asyncio
    async def test_wait_for_data_default_timeout(self, concrete_collector):
        """Test că wait_for_data() așteaptă timeout-ul default."""
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            await concrete_collector.wait_for_data()

            mock_sleep.assert_called_once_with(10.0)

    @pytest.mark.asyncio
    async def test_wait_for_data_custom_timeout(self, concrete_collector):
        """Test că wait_for_data() respectă timeout-ul custom."""
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            await concrete_collector.wait_for_data(timeout=5.0)

            mock_sleep.assert_called_once_with(5.0)


class TestBaseCollectorErrorHandling:
    """Teste pentru error handling și retry logic."""

    @pytest.mark.asyncio
    async def test_run_with_error_handling_calls_setup(self, concrete_collector):
        """Test că _run_with_error_handling() apelează setup()."""
        with patch.object(concrete_collector, 'setup', new=AsyncMock()) as mock_setup:
            with patch.object(concrete_collector, 'collect', new=AsyncMock()):
                concrete_collector._running = True

                # Pornește și oprește rapid
                task = asyncio.create_task(concrete_collector._run_with_error_handling())
                await asyncio.sleep(0.05)
                concrete_collector._running = False

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                mock_setup.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_error_handling_retries_on_error(self, concrete_collector):
        """Test că _run_with_error_handling() reîncearcă la eroare."""
        setup_call_count = 0

        async def failing_setup():
            nonlocal setup_call_count
            setup_call_count += 1
            if setup_call_count < 3:
                raise Exception("Setup failed")

        with patch.object(concrete_collector, 'setup', new=failing_setup):
            with patch.object(concrete_collector, 'collect', new=AsyncMock()):
                with patch('asyncio.sleep', new=AsyncMock()):
                    concrete_collector._running = True

                    task = asyncio.create_task(concrete_collector._run_with_error_handling())
                    await asyncio.sleep(0.1)
                    concrete_collector._running = False

                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                    # Verifică că setup a fost încercat de mai multe ori
                    assert setup_call_count >= 2

    @pytest.mark.asyncio
    async def test_run_with_error_handling_stops_after_max_retries(self):
        """Test că _run_with_error_handling() se oprește după max retries."""
        mock_browser_manager = AsyncMock()
        collector = ConcreteCollector(mock_browser_manager)

        async def always_failing_setup():
            raise Exception("Setup always fails")

        with patch.object(collector, 'setup', new=always_failing_setup):
            with patch('asyncio.sleep', new=AsyncMock()):
                await collector.start()

                # Așteaptă să se oprească
                max_wait = 2.0
                start_time = asyncio.get_event_loop().time()
                while collector._running:
                    await asyncio.sleep(0.1)
                    if asyncio.get_event_loop().time() - start_time > max_wait:
                        break

                # Verifică că s-a oprit
                assert collector._running is False


class TestBaseCollectorAsyncContextManager:
    """Teste pentru funcționalitatea de async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager_starts_and_stops(self, concrete_collector):
        """Test că async context manager pornește și oprește collector-ul."""
        with patch.object(concrete_collector, 'setup', new=AsyncMock()):
            with patch.object(concrete_collector, 'cleanup', new=AsyncMock()):
                async with concrete_collector as collector:
                    # În timpul context-ului, ar trebui să ruleze
                    await asyncio.sleep(0.05)
                    assert collector._running is True

                # După ieșirea din context, ar trebui oprit
                assert concrete_collector._running is False

    @pytest.mark.asyncio
    async def test_context_manager_cleanup_on_exception(self, concrete_collector):
        """Test că context manager face cleanup chiar dacă apare excepție."""
        with patch.object(concrete_collector, 'setup', new=AsyncMock()):
            with patch.object(concrete_collector, 'cleanup', new=AsyncMock()) as mock_cleanup:
                with pytest.raises(ValueError):
                    async with concrete_collector:
                        await asyncio.sleep(0.05)
                        raise ValueError("Test exception")

                # Verifică că cleanup a fost apelat oricum
                mock_cleanup.assert_called()


class TestBaseCollectorIntegration:
    """Teste de integrare pentru workflow complet."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test workflow complet: start -> collect -> stop."""
        mock_browser_manager = AsyncMock()
        mock_page = AsyncMock()
        mock_page.is_closed.return_value = False
        mock_browser_manager.new_page.return_value = mock_page

        collector = ConcreteCollector(mock_browser_manager, sport="football")

        with patch('src.collectors.base.create_interceptor', new=AsyncMock()):
            with patch('src.collectors.base.create_ws_interceptor', new=AsyncMock()):
                # Start
                await collector.start()
                assert collector.is_running() is True

                # Așteaptă să ruleze puțin
                await asyncio.sleep(0.15)

                # Verifică că collect() a fost apelat
                assert collector.collect_called is True

                # Stop
                await collector.stop()
                assert collector.is_running() is False
