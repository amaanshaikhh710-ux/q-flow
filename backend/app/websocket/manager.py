"""Connection manager for real-time WebSocket subscriptions and broadcasting."""

import asyncio
import logging
import uuid
from typing import Dict, Set, Any
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for patient entries and staff queue monitors."""

    def __init__(self):
        self._lock = asyncio.Lock()
        # entry_id -> Set[WebSocket]
        self._patient_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        # queue_id -> Set[WebSocket]
        self._queue_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        # user_id -> Set[WebSocket] (for patient/staff user-level notifications & updates)
        self._user_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        # hospital_id -> Set[WebSocket] (for staff hospital operations overview updates)
        self._hospital_connections: Dict[uuid.UUID, Set[WebSocket]] = {}

    async def connect_patient(self, entry_id: uuid.UUID, websocket: WebSocket) -> None:
        """Register patient WebSocket connection for their specific queue entry."""
        await websocket.accept()
        async with self._lock:
            if entry_id not in self._patient_connections:
                self._patient_connections[entry_id] = set()
            self._patient_connections[entry_id].add(websocket)
        logger.info("Patient connected to entry %s. Active connections: %d", entry_id, len(self._patient_connections[entry_id]))

    async def disconnect_patient(self, entry_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister patient WebSocket connection."""
        async with self._lock:
            if entry_id in self._patient_connections:
                self._patient_connections[entry_id].discard(websocket)
                if not self._patient_connections[entry_id]:
                    del self._patient_connections[entry_id]
        logger.info("Patient disconnected from entry %s", entry_id)

    async def connect_queue(self, queue_id: uuid.UUID, websocket: WebSocket) -> None:
        """Register staff WebSocket connection for full queue monitoring."""
        await websocket.accept()
        async with self._lock:
            if queue_id not in self._queue_connections:
                self._queue_connections[queue_id] = set()
            self._queue_connections[queue_id].add(websocket)
        logger.info("Staff connected to queue %s. Active staff connections: %d", queue_id, len(self._queue_connections[queue_id]))

    async def disconnect_queue(self, queue_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister staff WebSocket connection."""
        async with self._lock:
            if queue_id in self._queue_connections:
                self._queue_connections[queue_id].discard(websocket)
                if not self._queue_connections[queue_id]:
                    del self._queue_connections[queue_id]
        logger.info("Staff disconnected from queue %s", queue_id)

    async def connect_user(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Register user-level WebSocket connection for real-time notifications & dashboard updates."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(websocket)
        logger.info("User connected %s. Active connections: %d", user_id, len(self._user_connections[user_id]))

    async def disconnect_user(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister user-level WebSocket connection."""
        async with self._lock:
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(websocket)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]
        logger.info("User disconnected %s", user_id)

    async def connect_hospital(self, hospital_id: uuid.UUID, websocket: WebSocket) -> None:
        """Register staff connection for hospital-level operations updates."""
        await websocket.accept()
        async with self._lock:
            if hospital_id not in self._hospital_connections:
                self._hospital_connections[hospital_id] = set()
            self._hospital_connections[hospital_id].add(websocket)
        logger.info("Staff connected to hospital %s. Active connections: %d", hospital_id, len(self._hospital_connections[hospital_id]))

    async def disconnect_hospital(self, hospital_id: uuid.UUID, websocket: WebSocket) -> None:
        """Unregister staff connection from hospital-level updates."""
        async with self._lock:
            if hospital_id in self._hospital_connections:
                self._hospital_connections[hospital_id].discard(websocket)
                if not self._hospital_connections[hospital_id]:
                    del self._hospital_connections[hospital_id]
        logger.info("Staff disconnected from hospital %s", hospital_id)

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """Send a direct JSON message to a single WebSocket client."""
        try:
            await websocket.send_json(jsonable_encoder(message))
        except Exception as e:
            logger.warning("Failed to send message to websocket client: %s", e)

    async def send_to_patient(self, entry_id: uuid.UUID, message: dict) -> int:
        """Send message to all active WebSocket clients subscribed to a specific patient entry.

        Returns the number of successfully delivered connections.
        Stale/closed connections are automatically cleaned up.
        """
        async with self._lock:
            sockets = list(self._patient_connections.get(entry_id, set()))

        if not sockets:
            return 0

        delivered = 0
        stale_sockets = []
        encoded = jsonable_encoder(message)

        for ws in sockets:
            try:
                await ws.send_json(encoded)
                delivered += 1
            except Exception as e:
                logger.warning("Error delivering to patient socket for entry %s: %s", entry_id, e)
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                if entry_id in self._patient_connections:
                    for ws in stale_sockets:
                        self._patient_connections[entry_id].discard(ws)
                    if not self._patient_connections[entry_id]:
                        del self._patient_connections[entry_id]

        return delivered

    async def send_to_user(self, user_id: uuid.UUID, message: dict) -> int:
        """Send message to all active WebSocket clients for a specific user (e.g. notifications/dashboard)."""
        async with self._lock:
            sockets = list(self._user_connections.get(user_id, set()))

        if not sockets:
            return 0

        delivered = 0
        stale_sockets = []
        encoded = jsonable_encoder(message)

        for ws in sockets:
            try:
                await ws.send_json(encoded)
                delivered += 1
            except Exception as e:
                logger.warning("Error delivering to user socket %s: %s", user_id, e)
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                if user_id in self._user_connections:
                    for ws in stale_sockets:
                        self._user_connections[user_id].discard(ws)
                    if not self._user_connections[user_id]:
                        del self._user_connections[user_id]

        return delivered

    async def broadcast_to_queue(self, queue_id: uuid.UUID, message: dict) -> int:
        """Broadcast message to all active staff WebSocket connections monitoring the queue.

        Returns the number of successfully delivered connections.
        """
        async with self._lock:
            sockets = list(self._queue_connections.get(queue_id, set()))

        if not sockets:
            return 0

        delivered = 0
        stale_sockets = []
        encoded = jsonable_encoder(message)

        for ws in sockets:
            try:
                await ws.send_json(encoded)
                delivered += 1
            except Exception as e:
                logger.warning("Error broadcasting to staff socket for queue %s: %s", queue_id, e)
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                if queue_id in self._queue_connections:
                    for ws in stale_sockets:
                        self._queue_connections[queue_id].discard(ws)
                    if not self._queue_connections[queue_id]:
                        del self._queue_connections[queue_id]

        return delivered

    async def broadcast_to_hospital(self, hospital_id: uuid.UUID, message: dict) -> int:
        """Broadcast message to all active staff WebSocket connections monitoring the hospital."""
        async with self._lock:
            sockets = list(self._hospital_connections.get(hospital_id, set()))

        if not sockets:
            return 0

        delivered = 0
        stale_sockets = []
        encoded = jsonable_encoder(message)

        for ws in sockets:
            try:
                await ws.send_json(encoded)
                delivered += 1
            except Exception as e:
                logger.warning("Error broadcasting to hospital socket %s: %s", hospital_id, e)
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                if hospital_id in self._hospital_connections:
                    for ws in stale_sockets:
                        self._hospital_connections[hospital_id].discard(ws)
                    if not self._hospital_connections[hospital_id]:
                        del self._hospital_connections[hospital_id]

        return delivered

    def get_patient_connection_count(self, entry_id: uuid.UUID) -> int:
        """Count active sockets for a patient entry."""
        return len(self._patient_connections.get(entry_id, set()))

    def get_queue_connection_count(self, queue_id: uuid.UUID) -> int:
        """Count active staff sockets for a queue."""
        return len(self._queue_connections.get(queue_id, set()))

    def get_user_connection_count(self, user_id: uuid.UUID) -> int:
        """Count active sockets for a user."""
        return len(self._user_connections.get(user_id, set()))

    def get_hospital_connection_count(self, hospital_id: uuid.UUID) -> int:
        """Count active sockets for a hospital."""
        return len(self._hospital_connections.get(hospital_id, set()))


# Global manager singleton
connection_manager = ConnectionManager()

