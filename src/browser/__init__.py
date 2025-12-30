"""Browser automation module for SofaScore data collection."""

from .manager import BrowserManager
from .interceptor import ResponseInterceptor, create_interceptor, API_PATTERNS
from .ws_interceptor import (
    WebSocketInterceptor,
    LiveScoreWebSocketInterceptor,
    create_ws_interceptor,
)

__all__ = [
    "BrowserManager",
    "ResponseInterceptor",
    "create_interceptor",
    "API_PATTERNS",
    "WebSocketInterceptor",
    "LiveScoreWebSocketInterceptor",
    "create_ws_interceptor",
]
