"""WebSocket package exports."""

from app.websocket.manager import ConnectionManager, connection_manager
from app.websocket.schemas import WebSocketEventType, WebSocketMessage, PatientQueueSnapshot
from app.websocket.snapshot_service import WebSocketSnapshotService
from app.websocket.handlers import router as websocket_router

__all__ = [
    "ConnectionManager",
    "connection_manager",
    "WebSocketEventType",
    "WebSocketMessage",
    "PatientQueueSnapshot",
    "WebSocketSnapshotService",
    "websocket_router",
]
