"""
Pytest configuration și fixtures globale pentru toate testele.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """
    Creează un event loop pentru sesiunea de teste.
    Necesar pentru testele async cu pytest-asyncio.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_playwright():
    """Mock pentru Playwright instance."""
    mock = AsyncMock()
    mock.chromium = AsyncMock()
    mock.stop = AsyncMock()
    return mock


@pytest.fixture
def mock_browser():
    """Mock pentru Browser instance."""
    mock = AsyncMock()
    mock.new_context = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_context():
    """Mock pentru BrowserContext instance."""
    mock = AsyncMock()
    mock.new_page = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_page():
    """Mock pentru Page instance."""
    mock = AsyncMock()
    mock.goto = AsyncMock()
    mock.wait_for_load_state = AsyncMock()
    mock.on = MagicMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_response():
    """Mock pentru Response instance."""
    mock = MagicMock()
    mock.url = "https://www.sofascore.com/api/v1/test"
    mock.status = 200
    mock.ok = True
    mock.json = AsyncMock(return_value={"test": "data"})
    mock.text = AsyncMock(return_value='{"test": "data"}')
    return mock


@pytest.fixture
def mock_websocket():
    """Mock pentru WebSocket instance."""
    mock = AsyncMock()
    mock.url = "wss://www.sofascore.com/ws"
    mock.on = MagicMock()
    return mock


@pytest.fixture
def mock_browser_manager():
    """Mock pentru BrowserManager instance."""
    from src.browser.manager import BrowserManager
    mock = AsyncMock(spec=BrowserManager)
    mock.new_page = AsyncMock()
    mock.create_context = AsyncMock()
    mock.get_context = AsyncMock()
    mock.close_context = AsyncMock()
    mock.shutdown = AsyncMock()
    return mock


@pytest.fixture
def mock_http_interceptor():
    """Mock pentru HTTP ResponseInterceptor instance."""
    mock = MagicMock()
    mock.on = MagicMock()
    mock.clear_handlers = MagicMock()
    return mock


@pytest.fixture
def mock_ws_interceptor():
    """Mock pentru WebSocket interceptor instance."""
    mock = MagicMock()
    mock.on_message = MagicMock()
    mock.on_score_update = MagicMock()
    mock.on_incident = MagicMock()
    mock.clear_handlers = MagicMock()
    mock.active_connections = 0
    return mock


# Configurare pytest-asyncio
def pytest_configure(config):
    """Configurare pytest pentru testele async."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
