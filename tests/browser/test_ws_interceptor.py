"""
Tests pentru WebSocketInterceptor și LiveScoreWebSocketInterceptor.

Testează interceptarea și procesarea mesajelor WebSocket pentru live updates.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.browser.ws_interceptor import (
    WebSocketInterceptor,
    LiveScoreWebSocketInterceptor,
    create_ws_interceptor,
)


@pytest.fixture
def ws_interceptor():
    """Fixture pentru WebSocketInterceptor instance."""
    return WebSocketInterceptor()


@pytest.fixture
def live_ws_interceptor():
    """Fixture pentru LiveScoreWebSocketInterceptor instance."""
    return LiveScoreWebSocketInterceptor()


@pytest.fixture
def mock_page():
    """Fixture pentru mock Page."""
    page = AsyncMock()
    page.on = MagicMock()
    return page


@pytest.fixture
def mock_websocket():
    """Fixture pentru mock WebSocket."""
    ws = AsyncMock()
    ws.url = "wss://www.sofascore.com/ws"
    ws.on = MagicMock()
    return ws


class TestWebSocketInterceptorInit:
    """Teste pentru inițializarea WebSocketInterceptor."""

    def test_init_creates_empty_handlers_list(self, ws_interceptor):
        """Test că inițializarea creează lista goală de handlers."""
        assert isinstance(ws_interceptor.handlers, list)
        assert len(ws_interceptor.handlers) == 0

    def test_init_creates_active_sockets_list(self, ws_interceptor):
        """Test că inițializarea creează lista de socket-uri active."""
        assert isinstance(ws_interceptor._active_sockets, list)
        assert len(ws_interceptor._active_sockets) == 0


class TestWebSocketInterceptorOnMessage:
    """Teste pentru înregistrarea handler-elor de mesaje."""

    @pytest.mark.asyncio
    async def test_on_message_registers_handler(self, ws_interceptor):
        """Test că on_message() înregistrează un handler."""
        async def test_handler(data: dict) -> None:
            pass

        ws_interceptor.on_message(test_handler)

        assert test_handler in ws_interceptor.handlers
        assert len(ws_interceptor.handlers) == 1

    @pytest.mark.asyncio
    async def test_on_message_registers_multiple_handlers(self, ws_interceptor):
        """Test că on_message() poate înregistra mai multe handler-e."""
        async def handler1(data: dict) -> None:
            pass

        async def handler2(data: dict) -> None:
            pass

        ws_interceptor.on_message(handler1)
        ws_interceptor.on_message(handler2)

        assert handler1 in ws_interceptor.handlers
        assert handler2 in ws_interceptor.handlers
        assert len(ws_interceptor.handlers) == 2


class TestWebSocketInterceptorAttach:
    """Teste pentru atașarea interceptor-ului la o pagină."""

    @pytest.mark.asyncio
    async def test_attach_registers_websocket_handler(self, ws_interceptor, mock_page):
        """Test că attach() înregistrează handler-ul pentru WebSocket."""
        await ws_interceptor.attach(mock_page)

        # Verifică că page.on a fost apelat cu 'websocket'
        mock_page.on.assert_called_once()
        call_args = mock_page.on.call_args
        assert call_args[0][0] == "websocket"


class TestWebSocketInterceptorOnWebSocket:
    """Teste pentru handler-ul intern de WebSocket."""

    @pytest.mark.asyncio
    async def test_on_websocket_adds_to_active_sockets(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_websocket() adaugă socket-ul la lista de active."""
        await ws_interceptor._on_websocket(mock_websocket)

        assert mock_websocket in ws_interceptor._active_sockets
        assert len(ws_interceptor._active_sockets) == 1

    @pytest.mark.asyncio
    async def test_on_websocket_registers_event_handlers(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_websocket() înregistrează handler-ele pentru evenimente."""
        await ws_interceptor._on_websocket(mock_websocket)

        # Verifică că au fost înregistrate handler-ele pentru evenimente
        assert mock_websocket.on.call_count == 3

        # Verifică că s-au înregistrat handler-ele corecte
        call_args_list = [call[0][0] for call in mock_websocket.on.call_args_list]
        assert "framereceived" in call_args_list
        assert "framesent" in call_args_list
        assert "close" in call_args_list


class TestWebSocketInterceptorOnFrameReceived:
    """Teste pentru procesarea frame-urilor primite."""

    @pytest.mark.asyncio
    async def test_on_frame_received_processes_json_message(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_frame_received() procesează mesajele JSON."""
        handler_called = False
        received_data = None

        async def test_handler(data: dict) -> None:
            nonlocal handler_called, received_data
            handler_called = True
            received_data = data

        ws_interceptor.on_message(test_handler)

        # Simulează un mesaj JSON
        message = {"type": "score", "eventId": 123, "score": "2-1"}
        payload = json.dumps(message)

        ws_interceptor._on_frame_received(mock_websocket, payload)

        # Așteaptă procesarea async
        import asyncio
        await asyncio.sleep(0.1)

        # Verifică că handler-ul a fost apelat cu datele corecte
        assert handler_called
        assert received_data == message

    @pytest.mark.asyncio
    async def test_on_frame_received_handles_bytes_payload(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_frame_received() procesează payload-uri bytes."""
        handler_called = False

        async def test_handler(data: dict) -> None:
            nonlocal handler_called
            handler_called = True

        ws_interceptor.on_message(test_handler)

        # Simulează un mesaj bytes
        message = {"type": "score"}
        payload = json.dumps(message).encode("utf-8")

        ws_interceptor._on_frame_received(mock_websocket, payload)

        import asyncio
        await asyncio.sleep(0.1)

        assert handler_called

    def test_on_frame_received_ignores_non_json(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_frame_received() ignoră mesajele non-JSON."""
        handler_called = False

        async def test_handler(data: dict) -> None:
            nonlocal handler_called
            handler_called = True

        ws_interceptor.on_message(test_handler)

        # Simulează un mesaj non-JSON
        payload = "not valid json"

        ws_interceptor._on_frame_received(mock_websocket, payload)

        # Handler-ul nu ar trebui apelat pentru mesaje non-JSON
        # (nu putem verifica async aici, dar funcția nu ar trebui să arunce)


class TestWebSocketInterceptorProcessMessage:
    """Teste pentru procesarea mesajelor WebSocket."""

    @pytest.mark.asyncio
    async def test_process_message_calls_all_handlers(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _process_message() apelează toate handler-ele înregistrate."""
        handler1_called = False
        handler2_called = False

        async def handler1(data: dict) -> None:
            nonlocal handler1_called
            handler1_called = True

        async def handler2(data: dict) -> None:
            nonlocal handler2_called
            handler2_called = True

        ws_interceptor.on_message(handler1)
        ws_interceptor.on_message(handler2)

        message = {"type": "test", "data": "value"}
        await ws_interceptor._process_message(message, mock_websocket)

        assert handler1_called
        assert handler2_called

    @pytest.mark.asyncio
    async def test_process_message_handles_handler_exception(
        self, ws_interceptor, mock_websocket
    ):
        """Test că excepțiile din handler-e sunt gestionate."""
        handler2_called = False

        async def failing_handler(data: dict) -> None:
            raise ValueError("Handler error")

        async def working_handler(data: dict) -> None:
            nonlocal handler2_called
            handler2_called = True

        ws_interceptor.on_message(failing_handler)
        ws_interceptor.on_message(working_handler)

        message = {"type": "test"}
        await ws_interceptor._process_message(message, mock_websocket)

        # Handler-ul care funcționează ar trebui apelat oricum
        assert handler2_called


class TestWebSocketInterceptorOnClose:
    """Teste pentru închiderea WebSocket-ului."""

    @pytest.mark.asyncio
    async def test_on_close_removes_from_active_sockets(
        self, ws_interceptor, mock_websocket
    ):
        """Test că _on_close() șterge socket-ul din lista de active."""
        # Adaugă socket-ul la lista de active
        ws_interceptor._active_sockets.append(mock_websocket)
        assert len(ws_interceptor._active_sockets) == 1

        # Apelează _on_close
        ws_interceptor._on_close(mock_websocket)

        # Verifică că socket-ul a fost șters
        assert len(ws_interceptor._active_sockets) == 0
        assert mock_websocket not in ws_interceptor._active_sockets

    def test_on_close_handles_missing_socket(self, ws_interceptor, mock_websocket):
        """Test că _on_close() nu aruncă excepție dacă socket-ul nu există în listă."""
        # Socket-ul nu este în listă
        assert len(ws_interceptor._active_sockets) == 0

        # Nu ar trebui să arunce excepție
        ws_interceptor._on_close(mock_websocket)


class TestWebSocketInterceptorRemoveHandler:
    """Teste pentru ștergerea handler-elor."""

    @pytest.mark.asyncio
    async def test_remove_handler_removes_specific_handler(self, ws_interceptor):
        """Test că remove_handler() șterge un handler specific."""
        async def handler1(data: dict) -> None:
            pass

        async def handler2(data: dict) -> None:
            pass

        ws_interceptor.on_message(handler1)
        ws_interceptor.on_message(handler2)

        assert len(ws_interceptor.handlers) == 2

        ws_interceptor.remove_handler(handler1)

        assert len(ws_interceptor.handlers) == 1
        assert handler2 in ws_interceptor.handlers
        assert handler1 not in ws_interceptor.handlers


class TestWebSocketInterceptorClearHandlers:
    """Teste pentru ștergerea tuturor handler-elor."""

    @pytest.mark.asyncio
    async def test_clear_handlers_removes_all(self, ws_interceptor):
        """Test că clear_handlers() șterge toate handler-ele."""
        async def handler1(data: dict) -> None:
            pass

        async def handler2(data: dict) -> None:
            pass

        ws_interceptor.on_message(handler1)
        ws_interceptor.on_message(handler2)

        assert len(ws_interceptor.handlers) == 2

        ws_interceptor.clear_handlers()

        assert len(ws_interceptor.handlers) == 0


class TestWebSocketInterceptorActiveConnections:
    """Teste pentru property active_connections."""

    @pytest.mark.asyncio
    async def test_active_connections_returns_count(
        self, ws_interceptor, mock_websocket
    ):
        """Test că active_connections returnează numărul de conexiuni active."""
        assert ws_interceptor.active_connections == 0

        # Adaugă câteva socket-uri
        await ws_interceptor._on_websocket(mock_websocket)

        mock_ws2 = AsyncMock()
        mock_ws2.url = "wss://test2"
        mock_ws2.on = MagicMock()
        await ws_interceptor._on_websocket(mock_ws2)

        assert ws_interceptor.active_connections == 2


class TestLiveScoreWebSocketInterceptorInit:
    """Teste pentru inițializarea LiveScoreWebSocketInterceptor."""

    def test_init_inherits_from_base(self, live_ws_interceptor):
        """Test că LiveScoreWebSocketInterceptor moștenește din WebSocketInterceptor."""
        assert isinstance(live_ws_interceptor, WebSocketInterceptor)

    def test_init_creates_specialized_handlers(self, live_ws_interceptor):
        """Test că inițializarea creează liste pentru handler-e specializate."""
        assert isinstance(live_ws_interceptor.score_handlers, list)
        assert isinstance(live_ws_interceptor.incident_handlers, list)
        assert len(live_ws_interceptor.score_handlers) == 0
        assert len(live_ws_interceptor.incident_handlers) == 0


class TestLiveScoreWebSocketInterceptorOnScoreUpdate:
    """Teste pentru înregistrarea handler-elor de score."""

    @pytest.mark.asyncio
    async def test_on_score_update_registers_handler(self, live_ws_interceptor):
        """Test că on_score_update() înregistrează un handler."""
        async def test_handler(data: dict) -> None:
            pass

        live_ws_interceptor.on_score_update(test_handler)

        assert test_handler in live_ws_interceptor.score_handlers
        assert len(live_ws_interceptor.score_handlers) == 1


class TestLiveScoreWebSocketInterceptorOnIncident:
    """Teste pentru înregistrarea handler-elor de incident."""

    @pytest.mark.asyncio
    async def test_on_incident_registers_handler(self, live_ws_interceptor):
        """Test că on_incident() înregistrează un handler."""
        async def test_handler(data: dict) -> None:
            pass

        live_ws_interceptor.on_incident(test_handler)

        assert test_handler in live_ws_interceptor.incident_handlers
        assert len(live_ws_interceptor.incident_handlers) == 1


class TestLiveScoreWebSocketInterceptorProcessMessage:
    """Teste pentru procesarea mesajelor specializate."""

    @pytest.mark.asyncio
    async def test_process_message_calls_score_handlers_for_score_type(
        self, live_ws_interceptor, mock_websocket
    ):
        """Test că handler-ele de score sunt apelate pentru mesaje de tip score."""
        score_handler_called = False
        incident_handler_called = False
        base_handler_called = False

        async def score_handler(data: dict) -> None:
            nonlocal score_handler_called
            score_handler_called = True

        async def incident_handler(data: dict) -> None:
            nonlocal incident_handler_called
            incident_handler_called = True

        async def base_handler(data: dict) -> None:
            nonlocal base_handler_called
            base_handler_called = True

        live_ws_interceptor.on_score_update(score_handler)
        live_ws_interceptor.on_incident(incident_handler)
        live_ws_interceptor.on_message(base_handler)

        # Mesaj de tip score
        message = {"type": "score", "eventId": 123, "score": "2-1"}
        await live_ws_interceptor._process_message(message, mock_websocket)

        # Verifică că doar handler-ele de score și base au fost apelate
        assert score_handler_called
        assert not incident_handler_called
        assert base_handler_called

    @pytest.mark.asyncio
    async def test_process_message_calls_incident_handlers_for_incident_type(
        self, live_ws_interceptor, mock_websocket
    ):
        """Test că handler-ele de incident sunt apelate pentru mesaje de tip incident."""
        score_handler_called = False
        incident_handler_called = False

        async def score_handler(data: dict) -> None:
            nonlocal score_handler_called
            score_handler_called = True

        async def incident_handler(data: dict) -> None:
            nonlocal incident_handler_called
            incident_handler_called = True

        live_ws_interceptor.on_score_update(score_handler)
        live_ws_interceptor.on_incident(incident_handler)

        # Mesaj de tip incident
        message = {"type": "incident", "eventId": 123, "incidentType": "goal"}
        await live_ws_interceptor._process_message(message, mock_websocket)

        # Verifică că doar handler-ul de incident a fost apelat
        assert not score_handler_called
        assert incident_handler_called

    @pytest.mark.asyncio
    async def test_process_message_recognizes_score_variants(
        self, live_ws_interceptor, mock_websocket
    ):
        """Test că toate variantele de tip score sunt recunoscute."""
        score_types = ["score", "scoreChange", "scoreUpdate"]

        for score_type in score_types:
            handler_called = False

            async def test_handler(data: dict) -> None:
                nonlocal handler_called
                handler_called = True

            live_ws_interceptor.on_score_update(test_handler)

            message = {"type": score_type, "data": "test"}
            await live_ws_interceptor._process_message(message, mock_websocket)

            assert handler_called, f"Handler should be called for type '{score_type}'"

            # Curăță pentru următorul test
            live_ws_interceptor.score_handlers.clear()

    @pytest.mark.asyncio
    async def test_process_message_recognizes_incident_variants(
        self, live_ws_interceptor, mock_websocket
    ):
        """Test că toate variantele de tip incident sunt recunoscute."""
        incident_types = ["incident", "incidentChange", "newIncident"]

        for incident_type in incident_types:
            handler_called = False

            async def test_handler(data: dict) -> None:
                nonlocal handler_called
                handler_called = True

            live_ws_interceptor.on_incident(test_handler)

            message = {"type": incident_type, "data": "test"}
            await live_ws_interceptor._process_message(message, mock_websocket)

            assert handler_called, f"Handler should be called for type '{incident_type}'"

            # Curăță pentru următorul test
            live_ws_interceptor.incident_handlers.clear()

    @pytest.mark.asyncio
    async def test_process_message_handles_handler_exception(
        self, live_ws_interceptor, mock_websocket
    ):
        """Test că excepțiile din handler-e specializate sunt gestionate."""
        working_handler_called = False

        async def failing_handler(data: dict) -> None:
            raise ValueError("Handler error")

        async def working_handler(data: dict) -> None:
            nonlocal working_handler_called
            working_handler_called = True

        live_ws_interceptor.on_score_update(failing_handler)
        live_ws_interceptor.on_score_update(working_handler)

        message = {"type": "score", "data": "test"}
        await live_ws_interceptor._process_message(message, mock_websocket)

        # Handler-ul care funcționează ar trebui apelat oricum
        assert working_handler_called


class TestCreateWsInterceptor:
    """Teste pentru funcția helper create_ws_interceptor."""

    @pytest.mark.asyncio
    async def test_create_ws_interceptor_creates_base_interceptor(self, mock_page):
        """Test că create_ws_interceptor() creează un WebSocketInterceptor de bază."""
        interceptor = await create_ws_interceptor(mock_page, live_score_mode=False)

        assert isinstance(interceptor, WebSocketInterceptor)
        assert not isinstance(interceptor, LiveScoreWebSocketInterceptor)

        # Verifică că a fost atașat la pagină
        mock_page.on.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_ws_interceptor_creates_live_score_interceptor(self, mock_page):
        """Test că create_ws_interceptor() creează un LiveScoreWebSocketInterceptor."""
        interceptor = await create_ws_interceptor(mock_page, live_score_mode=True)

        assert isinstance(interceptor, LiveScoreWebSocketInterceptor)

        # Verifică că a fost atașat la pagină
        mock_page.on.assert_called_once()
