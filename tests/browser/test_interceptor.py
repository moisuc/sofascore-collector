"""
Tests pentru ResponseInterceptor class.

Testează interceptarea și procesarea răspunsurilor HTTP din API-ul SofaScore.
"""

import pytest
import re
from unittest.mock import AsyncMock, MagicMock, patch
from src.browser.interceptor import (
    ResponseInterceptor,
    create_interceptor,
    API_PATTERNS,
)


@pytest.fixture
def interceptor():
    """Fixture pentru ResponseInterceptor instance."""
    return ResponseInterceptor()


@pytest.fixture
def mock_page():
    """Fixture pentru mock Page."""
    page = AsyncMock()
    page.on = MagicMock()
    return page


@pytest.fixture
def mock_response():
    """Fixture pentru mock Response."""
    response = AsyncMock()
    response.url = "https://www.sofascore.com/api/v1/sport/football/events/live"
    response.status = 200
    response.ok = True
    response.headers = {"content-type": "application/json"}
    response.json = AsyncMock(return_value={"events": []})
    return response


class TestResponseInterceptorInit:
    """Teste pentru inițializarea ResponseInterceptor."""

    def test_init_creates_handlers_dict(self, interceptor):
        """Test că inițializarea creează dict-ul de handlers pentru toate pattern-urile."""
        # Verifică că există un entry pentru fiecare pattern
        for pattern_name in API_PATTERNS.keys():
            assert pattern_name in interceptor.handlers
            assert isinstance(interceptor.handlers[pattern_name], list)
            assert len(interceptor.handlers[pattern_name]) == 0

    def test_init_creates_queue(self, interceptor):
        """Test că inițializarea creează o coadă."""
        assert interceptor._queue is not None


class TestResponseInterceptorOn:
    """Teste pentru înregistrarea handler-elor."""

    @pytest.mark.asyncio
    async def test_on_registers_handler(self, interceptor):
        """Test că on() înregistrează un handler pentru un pattern."""
        async def test_handler(data: dict, match: re.Match) -> None:
            pass

        interceptor.on("live", test_handler)

        assert test_handler in interceptor.handlers["live"]
        assert len(interceptor.handlers["live"]) == 1

    @pytest.mark.asyncio
    async def test_on_registers_multiple_handlers_for_same_pattern(self, interceptor):
        """Test că on() poate înregistra mai multe handler-e pentru același pattern."""
        async def handler1(data: dict, match: re.Match) -> None:
            pass

        async def handler2(data: dict, match: re.Match) -> None:
            pass

        interceptor.on("live", handler1)
        interceptor.on("live", handler2)

        assert handler1 in interceptor.handlers["live"]
        assert handler2 in interceptor.handlers["live"]
        assert len(interceptor.handlers["live"]) == 2

    def test_on_raises_for_unknown_pattern(self, interceptor):
        """Test că on() aruncă excepție pentru pattern necunoscut."""
        async def test_handler(data: dict, match: re.Match) -> None:
            pass

        with pytest.raises(ValueError, match="Unknown pattern"):
            interceptor.on("unknown_pattern", test_handler)


class TestResponseInterceptorAttach:
    """Teste pentru atașarea interceptor-ului la o pagină."""

    @pytest.mark.asyncio
    async def test_attach_registers_response_handler(self, interceptor, mock_page):
        """Test că attach() înregistrează handler-ul pentru răspunsuri."""
        await interceptor.attach(mock_page)

        # Verifică că page.on a fost apelat cu 'response'
        mock_page.on.assert_called_once()
        call_args = mock_page.on.call_args
        assert call_args[0][0] == "response"


class TestResponseInterceptorProcessResponse:
    """Teste pentru procesarea răspunsurilor."""

    @pytest.mark.asyncio
    async def test_process_response_with_matching_pattern(
        self, interceptor, mock_response
    ):
        """Test procesarea unui răspuns care se potrivește cu un pattern."""
        handler_called = False
        received_data = None
        received_match = None

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called, received_data, received_match
            handler_called = True
            received_data = data
            received_match = match

        interceptor.on("live", test_handler)

        # Procesează răspunsul
        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        # Așteaptă un pic pentru task-ul async
        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul a fost apelat
        assert handler_called
        assert received_data == {"events": []}
        assert received_match is not None

    @pytest.mark.asyncio
    async def test_process_response_skips_non_ok_response(self, interceptor):
        """Test că răspunsurile cu status != 200 sunt ignorate."""
        handler_called = False

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called
            handler_called = True

        interceptor.on("live", test_handler)

        # Mock răspuns cu status 404
        mock_response = AsyncMock()
        mock_response.url = "https://www.sofascore.com/api/v1/sport/football/events/live"
        mock_response.ok = False
        mock_response.status = 404

        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul NU a fost apelat
        assert not handler_called

    @pytest.mark.asyncio
    async def test_process_response_skips_non_json_content(self, interceptor):
        """Test că răspunsurile non-JSON sunt ignorate."""
        handler_called = False

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called
            handler_called = True

        interceptor.on("live", test_handler)

        # Mock răspuns cu content-type text/html
        mock_response = AsyncMock()
        mock_response.url = "https://www.sofascore.com/api/v1/sport/football/events/live"
        mock_response.ok = True
        mock_response.headers = {"content-type": "text/html"}

        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul NU a fost apelat
        assert not handler_called

    @pytest.mark.asyncio
    async def test_process_response_handles_json_parse_error(self, interceptor):
        """Test că erorile de parsare JSON sunt gestionate."""
        handler_called = False

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called
            handler_called = True

        interceptor.on("live", test_handler)

        # Mock răspuns care aruncă excepție la json()
        mock_response = AsyncMock()
        mock_response.url = "https://www.sofascore.com/api/v1/sport/football/events/live"
        mock_response.ok = True
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul NU a fost apelat
        assert not handler_called

    @pytest.mark.asyncio
    async def test_process_response_calls_multiple_handlers(self, interceptor, mock_response):
        """Test că toate handler-ele înregistrate pentru un pattern sunt apelate."""
        handler1_called = False
        handler2_called = False

        async def handler1(data: dict, match: re.Match) -> None:
            nonlocal handler1_called
            handler1_called = True

        async def handler2(data: dict, match: re.Match) -> None:
            nonlocal handler2_called
            handler2_called = True

        interceptor.on("live", handler1)
        interceptor.on("live", handler2)

        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că ambele handler-e au fost apelate
        assert handler1_called
        assert handler2_called

    @pytest.mark.asyncio
    async def test_process_response_handles_handler_exception(self, interceptor, mock_response):
        """Test că excepțiile din handler-e sunt gestionate fără a opri procesarea."""
        handler1_called = False
        handler2_called = False

        async def failing_handler(data: dict, match: re.Match) -> None:
            raise ValueError("Handler error")

        async def working_handler(data: dict, match: re.Match) -> None:
            nonlocal handler2_called
            handler2_called = True

        interceptor.on("live", failing_handler)
        interceptor.on("live", working_handler)

        pattern = API_PATTERNS["live"]
        match = pattern.search(mock_response.url)
        await interceptor._process_response(mock_response, "live", match)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul care funcționează a fost apelat oricum
        assert handler2_called


class TestResponseInterceptorOnResponse:
    """Teste pentru handler-ul intern _on_response."""

    @pytest.mark.asyncio
    async def test_on_response_matches_patterns(self, interceptor):
        """Test că _on_response detectează pattern-urile corecte."""
        handler_called = False
        matched_pattern = None

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called, matched_pattern
            handler_called = True
            matched_pattern = match.group(1) if match.groups() else None

        interceptor.on("live", test_handler)

        # Mock răspuns pentru live football
        mock_response = AsyncMock()
        mock_response.url = "https://www.sofascore.com/api/v1/sport/football/events/live"
        mock_response.ok = True
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = AsyncMock(return_value={"events": []})

        await interceptor._on_response(mock_response)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că pattern-ul a fost detectat corect
        assert handler_called
        assert matched_pattern == "football"

    @pytest.mark.asyncio
    async def test_on_response_ignores_non_matching_urls(self, interceptor):
        """Test că URL-urile care nu se potrivesc sunt ignorate."""
        handler_called = False

        async def test_handler(data: dict, match: re.Match) -> None:
            nonlocal handler_called
            handler_called = True

        interceptor.on("live", test_handler)

        # Mock răspuns cu URL care nu se potrivește
        mock_response = AsyncMock()
        mock_response.url = "https://www.sofascore.com/some/other/path"
        mock_response.ok = True
        mock_response.headers = {"content-type": "application/json"}

        await interceptor._on_response(mock_response)

        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul NU a fost apelat
        assert not handler_called


class TestResponseInterceptorRemoveHandler:
    """Teste pentru ștergerea handler-elor."""

    @pytest.mark.asyncio
    async def test_remove_handler_removes_specific_handler(self, interceptor):
        """Test că remove_handler() șterge un handler specific."""
        async def handler1(data: dict, match: re.Match) -> None:
            pass

        async def handler2(data: dict, match: re.Match) -> None:
            pass

        interceptor.on("live", handler1)
        interceptor.on("live", handler2)

        assert len(interceptor.handlers["live"]) == 2

        interceptor.remove_handler("live", handler1)

        assert len(interceptor.handlers["live"]) == 1
        assert handler2 in interceptor.handlers["live"]
        assert handler1 not in interceptor.handlers["live"]

    def test_remove_handler_does_nothing_if_not_found(self, interceptor):
        """Test că remove_handler() nu aruncă excepție dacă handler-ul nu există."""
        async def test_handler(data: dict, match: re.Match) -> None:
            pass

        # Nu înregistrăm handler-ul, doar încercăm să-l ștergem
        interceptor.remove_handler("live", test_handler)  # Nu ar trebui să arunce


class TestResponseInterceptorClearHandlers:
    """Teste pentru ștergerea tuturor handler-elor."""

    @pytest.mark.asyncio
    async def test_clear_handlers_for_specific_pattern(self, interceptor):
        """Test că clear_handlers() șterge toate handler-ele pentru un pattern."""
        async def handler1(data: dict, match: re.Match) -> None:
            pass

        async def handler2(data: dict, match: re.Match) -> None:
            pass

        interceptor.on("live", handler1)
        interceptor.on("live", handler2)
        interceptor.on("scheduled", handler1)

        assert len(interceptor.handlers["live"]) == 2
        assert len(interceptor.handlers["scheduled"]) == 1

        interceptor.clear_handlers("live")

        assert len(interceptor.handlers["live"]) == 0
        assert len(interceptor.handlers["scheduled"]) == 1  # Neschimbat

    @pytest.mark.asyncio
    async def test_clear_handlers_for_all_patterns(self, interceptor):
        """Test că clear_handlers(None) șterge toate handler-ele."""
        async def handler1(data: dict, match: re.Match) -> None:
            pass

        interceptor.on("live", handler1)
        interceptor.on("scheduled", handler1)

        assert len(interceptor.handlers["live"]) == 1
        assert len(interceptor.handlers["scheduled"]) == 1

        interceptor.clear_handlers(None)

        assert len(interceptor.handlers["live"]) == 0
        assert len(interceptor.handlers["scheduled"]) == 0


class TestCreateInterceptor:
    """Teste pentru funcția helper create_interceptor."""

    @pytest.mark.asyncio
    async def test_create_interceptor_creates_and_attaches(self, mock_page):
        """Test că create_interceptor() creează și atașează un interceptor."""
        interceptor = await create_interceptor(mock_page)

        # Verifică că interceptorul a fost creat
        assert isinstance(interceptor, ResponseInterceptor)

        # Verifică că a fost atașat la pagină
        mock_page.on.assert_called_once()
        call_args = mock_page.on.call_args
        assert call_args[0][0] == "response"


class TestAPIPatterns:
    """Teste pentru pattern-urile API definite."""

    def test_api_patterns_exist(self):
        """Test că pattern-urile necesare există."""
        assert "live" in API_PATTERNS
        assert "scheduled" in API_PATTERNS

    def test_live_pattern_matches_correct_urls(self):
        """Test că pattern-ul 'live' se potrivește cu URL-urile corecte."""
        pattern = API_PATTERNS["live"]

        # URL-uri care ar trebui să se potrivească
        valid_urls = [
            "/api/v1/sport/football/events/live",
            "/api/v1/sport/tennis/events/live",
            "/api/v1/sport/basketball/events/live",
        ]

        for url in valid_urls:
            match = pattern.search(url)
            assert match is not None, f"Pattern should match {url}"
            assert match.group(1) in ["football", "tennis", "basketball"]

    def test_scheduled_pattern_matches_correct_urls(self):
        """Test că pattern-ul 'scheduled' se potrivește cu URL-urile corecte."""
        pattern = API_PATTERNS["scheduled"]

        # URL-uri care ar trebui să se potrivească
        valid_urls = [
            "/api/v1/sport/football/scheduled-events/2024-01-15",
            "/api/v1/sport/tennis/scheduled-events/2024-12-31",
        ]

        for url in valid_urls:
            match = pattern.search(url)
            assert match is not None, f"Pattern should match {url}"
            assert match.group(1) in ["football", "tennis"]
            assert match.group(2) in ["2024-01-15", "2024-12-31"]

    def test_patterns_dont_match_invalid_urls(self):
        """Test că pattern-urile nu se potrivesc cu URL-uri invalide."""
        # URL-uri care NU ar trebui să se potrivească cu niciun pattern
        invalid_urls = [
            "/api/v1/sport/football/",
            "/api/v1/some/other/path",
            "/events/live",
            "/api/v2/sport/football/events/live",  # Versiune greșită
        ]

        for url in invalid_urls:
            for pattern_name, pattern in API_PATTERNS.items():
                match = pattern.search(url)
                assert match is None, f"Pattern {pattern_name} should not match {url}"
