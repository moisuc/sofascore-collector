"""
Tests pentru BrowserManager class.

Testează inițializarea, pornirea, crearea de contexte, refresh periodic și închiderea.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.browser.manager import BrowserManager


@pytest.fixture
def browser_manager():
    """Fixture pentru BrowserManager instance."""
    return BrowserManager(headless=True)


@pytest.fixture
def browser_manager_non_headless():
    """Fixture pentru BrowserManager instance în modul non-headless."""
    return BrowserManager(headless=False)


class TestBrowserManagerInit:
    """Teste pentru inițializarea BrowserManager."""

    def test_init_default_headless(self):
        """Test inițializare cu headless=True (default)."""
        manager = BrowserManager()
        assert manager.headless is True
        assert manager.playwright is None
        assert manager.browser is None
        assert manager.contexts == {}
        assert manager._refresh_tasks == {}

    def test_init_headless_true(self):
        """Test inițializare cu headless=True explicit."""
        manager = BrowserManager(headless=True)
        assert manager.headless is True
        assert manager.contexts == {}
        assert manager._refresh_tasks == {}

    def test_init_headless_false(self, browser_manager_non_headless):
        """Test inițializare cu headless=False."""
        assert browser_manager_non_headless.headless is False
        assert browser_manager_non_headless.contexts == {}
        assert browser_manager_non_headless._refresh_tasks == {}


class TestBrowserManagerStart:
    """Teste pentru pornirea browser-ului."""

    @pytest.mark.asyncio
    async def test_start_initializes_playwright(self, browser_manager):
        """Test că start() inițializează Playwright și pornește browser-ul."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium

        with patch(
            'src.browser.manager.async_playwright'
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            await browser_manager.start()

            # Verifică că Playwright a fost pornit
            mock_async_playwright.return_value.start.assert_called_once()

            # Verifică că browser-ul a fost lansat cu argumentele corecte
            mock_chromium.launch.assert_called_once_with(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )

            # Verifică că instanțele au fost setate
            assert browser_manager.playwright == mock_playwright
            assert browser_manager.browser == mock_browser

    @pytest.mark.asyncio
    async def test_start_with_headless_false(self, browser_manager_non_headless):
        """Test că start() respectă setarea headless=False."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium

        with patch(
            'src.browser.manager.async_playwright'
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            await browser_manager_non_headless.start()

            # Verifică că headless=False a fost trecut la launch
            mock_chromium.launch.assert_called_once_with(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )


class TestBrowserManagerCreateContext:
    """Teste pentru crearea de browser context."""

    @pytest.mark.asyncio
    async def test_create_context_default_name(self, browser_manager):
        """Test că create_context() creează un context cu numele 'default'."""
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager.browser = mock_browser

        result = await browser_manager.create_context()

        # Verifică că new_context a fost apelat
        assert mock_browser.new_context.called

        # Verifică că context-ul a fost returnat și adăugat cu numele 'default'
        assert result == mock_context
        assert 'default' in browser_manager.contexts
        assert browser_manager.contexts['default'] == mock_context

    @pytest.mark.asyncio
    async def test_create_context_custom_name(self, browser_manager):
        """Test crearea unui context cu nume custom."""
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager.browser = mock_browser

        result = await browser_manager.create_context(name="football")

        # Verifică că context-ul a fost adăugat cu numele corect
        assert result == mock_context
        assert 'football' in browser_manager.contexts
        assert browser_manager.contexts['football'] == mock_context

    @pytest.mark.asyncio
    async def test_create_context_raises_without_browser(self, browser_manager):
        """Test că create_context() aruncă excepție dacă browser-ul nu e pornit."""
        browser_manager.browser = None

        with pytest.raises(RuntimeError, match="Browser not started"):
            await browser_manager.create_context()

    @pytest.mark.asyncio
    async def test_create_context_returns_existing(self, browser_manager):
        """Test că create_context() returnează context-ul existent dacă numele există."""
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager.browser = mock_browser

        # Creează context prima dată
        ctx1 = await browser_manager.create_context(name="football")

        # Încearcă să creezi același context din nou
        ctx2 = await browser_manager.create_context(name="football")

        # Verifică că returnează același context
        assert ctx1 == ctx2
        assert mock_browser.new_context.call_count == 1  # Apelat o singură dată

    @pytest.mark.asyncio
    async def test_create_multiple_different_contexts(self, browser_manager):
        """Test crearea de contexte multiple cu nume diferite."""
        mock_ctx1 = AsyncMock()
        mock_ctx2 = AsyncMock()
        mock_ctx3 = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(
            side_effect=[mock_ctx1, mock_ctx2, mock_ctx3]
        )

        browser_manager.browser = mock_browser

        # Creează 3 contexte cu nume diferite
        ctx1 = await browser_manager.create_context(name="football")
        ctx2 = await browser_manager.create_context(name="tennis")
        ctx3 = await browser_manager.create_context(name="basketball")

        # Verifică că toate au fost create
        assert len(browser_manager.contexts) == 3
        assert browser_manager.contexts["football"] == mock_ctx1
        assert browser_manager.contexts["tennis"] == mock_ctx2
        assert browser_manager.contexts["basketball"] == mock_ctx3
        assert mock_browser.new_context.call_count == 3


class TestBrowserManagerGetContext:
    """Teste pentru obținerea unui context existent."""

    @pytest.mark.asyncio
    async def test_get_existing_context(self, browser_manager):
        """Test că get_context() returnează un context existent."""
        mock_context = AsyncMock()
        browser_manager.contexts["football"] = mock_context

        result = await browser_manager.get_context("football")
        assert result == mock_context

    @pytest.mark.asyncio
    async def test_get_non_existing_context(self, browser_manager):
        """Test că get_context() returnează None pentru context inexistent."""
        result = await browser_manager.get_context("non_existent")
        assert result is None


class TestBrowserManagerNewPage:
    """Teste pentru crearea de pagini noi."""

    @pytest.mark.asyncio
    async def test_new_page_in_existing_context(self, browser_manager):
        """Test crearea unei pagini noi într-un context existent."""
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        browser_manager.contexts["football"] = mock_context

        result = await browser_manager.new_page(context_name="football")

        assert result == mock_page
        mock_context.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_page_creates_context_if_missing(self, browser_manager):
        """Test că new_page() creează un context dacă nu există."""
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        browser_manager.browser = mock_browser

        result = await browser_manager.new_page(context_name="new_sport")

        # Verifică că context-ul a fost creat
        assert "new_sport" in browser_manager.contexts
        assert result == mock_page
        mock_context.new_page.assert_called_once()


class TestBrowserManagerRefresh:
    """Teste pentru funcționalitatea de refresh periodic."""

    @pytest.mark.asyncio
    async def test_refresh_page_periodically_starts_task(self, browser_manager):
        """Test că refresh_page_periodically() pornește un task."""
        mock_page = AsyncMock()

        await browser_manager.refresh_page_periodically(
            mock_page, interval=1, context_name="football"
        )

        # Verifică că task-ul a fost creat
        assert "football_refresh" in browser_manager._refresh_tasks

        # Cleanup
        await browser_manager.stop_refresh("football")

    @pytest.mark.asyncio
    async def test_stop_refresh_cancels_task(self, browser_manager):
        """Test că stop_refresh() oprește task-ul de refresh."""
        mock_page = AsyncMock()

        # Pornește refresh
        await browser_manager.refresh_page_periodically(
            mock_page, interval=10, context_name="football"
        )

        assert "football_refresh" in browser_manager._refresh_tasks

        # Oprește refresh
        await browser_manager.stop_refresh("football")

        # Verifică că task-ul a fost șters
        assert "football_refresh" not in browser_manager._refresh_tasks


class TestBrowserManagerCloseContext:
    """Teste pentru închiderea unui context specific."""

    @pytest.mark.asyncio
    async def test_close_context_removes_and_closes(self, browser_manager):
        """Test că close_context() închide și șterge context-ul."""
        mock_context = AsyncMock()
        browser_manager.contexts["football"] = mock_context

        await browser_manager.close_context("football")

        mock_context.close.assert_called_once()
        assert "football" not in browser_manager.contexts

    @pytest.mark.asyncio
    async def test_close_context_stops_refresh_task(self, browser_manager):
        """Test că close_context() oprește task-ul de refresh."""
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        browser_manager.contexts["football"] = mock_context

        # Pornește refresh
        await browser_manager.refresh_page_periodically(
            mock_page, interval=10, context_name="football"
        )

        # Închide context-ul
        await browser_manager.close_context("football")

        # Verifică că refresh-ul a fost oprit
        assert "football_refresh" not in browser_manager._refresh_tasks
        assert "football" not in browser_manager.contexts


class TestBrowserManagerShutdown:
    """Teste pentru închiderea completă a browser-ului."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_contexts(self, browser_manager):
        """Test că shutdown() închide toate contextele."""
        mock_ctx1 = AsyncMock()
        mock_ctx2 = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        browser_manager.contexts = {"football": mock_ctx1, "tennis": mock_ctx2}
        browser_manager.browser = mock_browser
        browser_manager.playwright = mock_playwright

        await browser_manager.shutdown()

        # Verifică că toate contextele au fost închise
        mock_ctx1.close.assert_called_once()
        mock_ctx2.close.assert_called_once()

        # Verifică că dict-ul a fost golit
        assert len(browser_manager.contexts) == 0

        # Verifică că browser-ul a fost închis
        mock_browser.close.assert_called_once()

        # Verifică că Playwright a fost oprit
        mock_playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_all_refresh_tasks(self, browser_manager):
        """Test că shutdown() oprește toate task-urile de refresh."""
        mock_page1 = AsyncMock()
        mock_page2 = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_ctx1 = AsyncMock()
        mock_ctx2 = AsyncMock()

        browser_manager.contexts = {"football": mock_ctx1, "tennis": mock_ctx2}
        browser_manager.browser = mock_browser
        browser_manager.playwright = mock_playwright

        # Pornește refresh pentru ambele contexte
        await browser_manager.refresh_page_periodically(
            mock_page1, interval=10, context_name="football"
        )
        await browser_manager.refresh_page_periodically(
            mock_page2, interval=10, context_name="tennis"
        )

        # Verifică că task-urile există
        assert len(browser_manager._refresh_tasks) == 2

        # Shutdown
        await browser_manager.shutdown()

        # Verifică că task-urile au fost oprite
        assert len(browser_manager._refresh_tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_with_no_contexts(self, browser_manager):
        """Test shutdown() când nu există contexte."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        browser_manager.contexts = {}
        browser_manager.browser = mock_browser
        browser_manager.playwright = mock_playwright

        await browser_manager.shutdown()

        # Verifică că browser-ul și Playwright au fost închise
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()


class TestBrowserManagerAsyncContextManager:
    """Teste pentru funcționalitatea de async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test că BrowserManager funcționează ca async context manager."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium

        with patch(
            'src.browser.manager.async_playwright'
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            async with BrowserManager(headless=True) as manager:
                # Verifică că browser-ul a fost pornit
                assert manager.playwright is not None
                assert manager.browser is not None

            # Verifică că shutdown a fost apelat
            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_cleanup_on_exception(self):
        """Test că context manager face cleanup chiar dacă apare o excepție."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium

        with patch(
            'src.browser.manager.async_playwright'
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            with pytest.raises(ValueError):
                async with BrowserManager(headless=True) as manager:
                    # Verifică că browser-ul a fost pornit
                    assert manager.playwright is not None
                    # Simulează o excepție
                    raise ValueError("Test exception")

            # Verifică că shutdown a fost apelat oricum
            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()


class TestBrowserManagerIntegration:
    """Teste de integrare pentru workflow complet."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, browser_manager):
        """Test workflow complet: start -> create contexts -> new pages -> shutdown."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_chromium = AsyncMock()
        mock_context1 = AsyncMock()
        mock_context2 = AsyncMock()
        mock_page1 = AsyncMock()
        mock_page2 = AsyncMock()

        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium = mock_chromium
        mock_browser.new_context = AsyncMock(
            side_effect=[mock_context1, mock_context2]
        )
        mock_context1.new_page = AsyncMock(return_value=mock_page1)
        mock_context2.new_page = AsyncMock(return_value=mock_page2)

        with patch(
            'src.browser.manager.async_playwright'
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            # Start
            await browser_manager.start()
            assert browser_manager.playwright is not None
            assert browser_manager.browser is not None

            # Create contexts
            ctx1 = await browser_manager.create_context(name="football")
            ctx2 = await browser_manager.create_context(name="tennis")
            assert len(browser_manager.contexts) == 2

            # Create pages
            page1 = await browser_manager.new_page("football")
            page2 = await browser_manager.new_page("tennis")
            assert page1 == mock_page1
            assert page2 == mock_page2

            # Shutdown
            await browser_manager.shutdown()
            mock_context1.close.assert_called_once()
            mock_context2.close.assert_called_once()
            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()
