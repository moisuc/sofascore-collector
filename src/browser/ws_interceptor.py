"""WebSocket interceptor for capturing real-time updates."""

from playwright.async_api import Page, WebSocket
import asyncio
import json
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class WebSocketInterceptor:
    """
    Intercepts and processes WebSocket messages from SofaScore.

    Monitors WebSocket connections for real-time updates like
    live scores, incidents, and statistics changes.
    """

    def __init__(self):
        """Initialize WebSocket interceptor."""
        self.handlers: list[Callable[[dict], Awaitable[None]]] = []
        self._active_sockets: list[WebSocket] = []

    def on_message(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """
        Register a handler for WebSocket messages.

        Args:
            handler: Async function to handle the message data
                     Signature: async def handler(data: dict) -> None

        Example:
            async def handle_ws_message(data: dict) -> None:
                if data.get('type') == 'score':
                    print(f"Score update: {data}")

            ws_interceptor.on_message(handle_ws_message)
        """
        self.handlers.append(handler)
        logger.debug("Registered WebSocket message handler")

    async def attach(self, page: Page) -> None:
        """
        Attach interceptor to a Playwright page.

        Args:
            page: Playwright page to monitor
        """
        page.on("websocket", self._on_websocket)
        logger.info("WebSocket interceptor attached to page")

    async def _on_websocket(self, ws: WebSocket) -> None:
        """
        Internal handler for WebSocket connections.

        Args:
            ws: Playwright WebSocket object
        """
        url = ws.url
        logger.info(f"WebSocket connection opened: {url}")
        self._active_sockets.append(ws)

        # Register event handlers for this WebSocket
        ws.on("framereceived", lambda payload: self._on_frame_received(ws, payload))
        ws.on("framesent", lambda payload: self._on_frame_sent(ws, payload))
        ws.on("close", lambda: self._on_close(ws))

    def _on_frame_sent(self, ws: WebSocket, payload: dict) -> None:
        """
        Handle outgoing WebSocket frame.

        Args:
            ws: WebSocket instance
            payload: Frame payload
        """
        try:
            logger.debug(f"WS frame sent to {ws.url}: {payload}")
        except Exception as e:
            logger.error(f"Error logging sent frame: {e}")

    def _on_frame_received(self, ws: WebSocket, payload: dict) -> None:
        """
        Handle incoming WebSocket frame.

        Args:
            ws: WebSocket instance
            payload: Frame payload
        """
        try:
            # Payload is a string, parse it as JSON
            text = payload
            if isinstance(payload, bytes):
                text = payload.decode("utf-8")

            logger.debug(f"WS frame received from {ws.url}")

            # Try to parse as JSON
            try:
                data = json.loads(text)
                # Process the message asynchronously
                asyncio.create_task(self._process_message(data, ws))
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON WebSocket message: {text[:100]}")
        except Exception as e:
            logger.error(f"Error processing received frame: {e}", exc_info=True)

    async def _process_message(self, data: dict, ws: WebSocket) -> None:
        """
        Process a WebSocket message.

        Args:
            data: Parsed message data
            ws: WebSocket instance
        """
        try:
            logger.debug(f"Processing WS message: {data.get('type', 'unknown')}")

            # Call all registered handlers
            if self.handlers:
                for handler in self.handlers:
                    try:
                        await handler(data)
                    except Exception as e:
                        logger.error(
                            f"Handler error for WebSocket message: {e}", exc_info=True
                        )
            else:
                logger.debug("No handlers registered for WebSocket messages")

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)

    def _on_close(self, ws: WebSocket) -> None:
        """
        Handle WebSocket close event.

        Args:
            ws: WebSocket instance
        """
        logger.info(f"WebSocket connection closed: {ws.url}")
        if ws in self._active_sockets:
            self._active_sockets.remove(ws)

    def remove_handler(self, handler: Callable) -> None:
        """
        Remove a specific message handler.

        Args:
            handler: Handler function to remove
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.debug("Removed WebSocket message handler")

    def clear_handlers(self) -> None:
        """Clear all message handlers."""
        self.handlers.clear()
        logger.debug("Cleared all WebSocket message handlers")

    @property
    def active_connections(self) -> int:
        """Get count of active WebSocket connections."""
        return len(self._active_sockets)


class LiveScoreWebSocketInterceptor(WebSocketInterceptor):
    """
    Specialized WebSocket interceptor for live score updates.

    Filters and processes only score-related messages.
    """

    def __init__(self):
        """Initialize live score WebSocket interceptor."""
        super().__init__()
        self.score_handlers: list[Callable[[dict], Awaitable[None]]] = []
        self.incident_handlers: list[Callable[[dict], Awaitable[None]]] = []

    def on_score_update(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """
        Register handler for score updates.

        Args:
            handler: Async function to handle score updates
        """
        self.score_handlers.append(handler)
        logger.debug("Registered score update handler")

    def on_incident(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """
        Register handler for match incidents.

        Args:
            handler: Async function to handle incidents
        """
        self.incident_handlers.append(handler)
        logger.debug("Registered incident handler")

    async def _process_message(self, data: dict, ws: WebSocket) -> None:
        """
        Process WebSocket message with type filtering.

        Args:
            data: Parsed message data
            ws: WebSocket instance
        """
        # Call parent processing
        await super()._process_message(data, ws)

        # Handle specific message types
        message_type = data.get("type", "")

        if message_type in ("score", "scoreChange", "scoreUpdate"):
            for handler in self.score_handlers:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Score handler error: {e}", exc_info=True)

        elif message_type in ("incident", "incidentChange", "newIncident"):
            for handler in self.incident_handlers:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Incident handler error: {e}", exc_info=True)


async def create_ws_interceptor(
    page: Page, live_score_mode: bool = False
) -> WebSocketInterceptor:
    """
    Create and attach a WebSocket interceptor to a page.

    Args:
        page: Playwright page to monitor
        live_score_mode: Use specialized live score interceptor

    Returns:
        WebSocketInterceptor instance

    Example:
        ws_interceptor = await create_ws_interceptor(page, live_score_mode=True)
        ws_interceptor.on_score_update(my_score_handler)
        await page.goto('https://www.sofascore.com/football/livescore')
    """
    if live_score_mode:
        interceptor = LiveScoreWebSocketInterceptor()
    else:
        interceptor = WebSocketInterceptor()

    await interceptor.attach(page)
    return interceptor
