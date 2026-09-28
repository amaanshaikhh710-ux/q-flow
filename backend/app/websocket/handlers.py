"""WebSocket endpoint route handlers."""

import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.websocket.manager import connection_manager
from app.websocket.auth import (
    authenticate_websocket_user,
    authorize_patient_entry,
    authorize_staff_queue,
    WS_CLOSE_POLICY_VIOLATION,
)
from app.websocket.snapshot_service import WebSocketSnapshotService
from app.services.queue_engine import QueueEngineService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/patient/{entry_id}")
async def websocket_patient_endpoint(
    websocket: WebSocket,
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Patient-specific real-time WebSocket connection.

    Authentication: JWT via 'token' query param or 'Authorization: Bearer' header.
    Authorization: Patient can ONLY access their own ticket.
    """
    user = authenticate_websocket_user(websocket, db)
    if not user:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="Unauthorized: Missing or invalid token")
        return

    authorized, entry, reason = authorize_patient_entry(db, user, entry_id)
    if not authorized or not entry:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason=reason)
        return

    # Accept connection and register with connection manager
    await connection_manager.connect_patient(entry.id, websocket)

    try:
        now = datetime.now(timezone.utc)
        # 1. Send initial QUEUE_CONNECTED event
        await connection_manager.send_personal_message(
            websocket,
            {
                "type": "QUEUE_CONNECTED",
                "version": 1,
                "timestamp": now.isoformat(),
                "entry_id": str(entry.id),
                "queue_id": str(entry.queue_id),
                "message": "Connected to patient queue live updates",
            },
        )

        # 2. Send fresh authoritative QUEUE_SNAPSHOT (supports reconnect)
        snapshot = WebSocketSnapshotService.build_patient_snapshot(db, entry)
        await connection_manager.send_personal_message(websocket, snapshot)

        # 3. Keep connection alive and await client heartbeat / disconnect
        while True:
            _ = await websocket.receive_text()

    except WebSocketDisconnect:
        await connection_manager.disconnect_patient(entry.id, websocket)
    except Exception as e:
        logger.warning("WebSocket exception for patient entry %s: %s", entry_id, e)
        await connection_manager.disconnect_patient(entry.id, websocket)


@router.websocket("/queue/{queue_id}")
async def websocket_staff_queue_endpoint(
    websocket: WebSocket,
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Staff queue-level real-time WebSocket connection for Reception Control Center.

    Authentication: JWT via 'token' query param or 'Authorization: Bearer' header.
    Authorization: Only STAFF and ADMIN roles allowed.
    """
    user = authenticate_websocket_user(websocket, db)
    if not user:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="Unauthorized: Missing or invalid token")
        return

    authorized, queue, reason = authorize_staff_queue(db, user, queue_id)
    if not authorized or not queue:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason=reason)
        return

    # Accept connection and register with connection manager
    await connection_manager.connect_queue(queue.id, websocket)

    try:
        now = datetime.now(timezone.utc)
        # 1. Send QUEUE_CONNECTED
        await connection_manager.send_personal_message(
            websocket,
            {
                "type": "QUEUE_CONNECTED",
                "version": 1,
                "timestamp": now.isoformat(),
                "queue_id": str(queue.id),
                "message": "Connected to staff queue monitor",
            },
        )

        # 2. Send current queue snapshot
        snapshot_data = QueueEngineService.get_queue_snapshot(db, queue.id)
        # Format as staff-safe snapshot message
        staff_snapshot = {
            "type": "QUEUE_SNAPSHOT",
            "version": 1,
            "timestamp": now.isoformat(),
            "queue_id": str(queue.id),
            "payload": {
                "queue_id": str(queue.id),
                "queue_name": snapshot_data.get("queue_name"),
                "queue_status": snapshot_data.get("status").value if hasattr(snapshot_data.get("status"), "value") else str(snapshot_data.get("status")),
                "doctor_name": snapshot_data.get("doctor_name"),
                "department_name": snapshot_data.get("department_name"),
                "currently_serving": snapshot_data.get("currently_serving").model_dump() if snapshot_data.get("currently_serving") else None,
                "currently_called": snapshot_data.get("currently_called").model_dump() if snapshot_data.get("currently_called") else None,
                "next_patient": snapshot_data.get("next_patient").model_dump() if snapshot_data.get("next_patient") else None,
                "waiting_count": snapshot_data.get("total_waiting", 0),
                "in_consultation_count": snapshot_data.get("total_in_consultation", 0),
                "completed_count": snapshot_data.get("total_completed", 0),
                "no_show_count": snapshot_data.get("total_no_show", 0),
            },
        }
        await connection_manager.send_personal_message(websocket, staff_snapshot)

        # 3. Keep alive
        while True:
            _ = await websocket.receive_text()

    except WebSocketDisconnect:
        await connection_manager.disconnect_queue(queue.id, websocket)
    except Exception as e:
        logger.warning("WebSocket exception for staff queue %s: %s", queue_id, e)
        await connection_manager.disconnect_queue(queue.id, websocket)


@router.websocket("/user")
async def websocket_user_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """User-level real-time WebSocket connection for personal dashboard and notification updates.

    Authentication: JWT via 'token' query param or 'Authorization: Bearer' header.
    """
    user = authenticate_websocket_user(websocket, db)
    if not user:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="Unauthorized: Missing or invalid token")
        return

    await connection_manager.connect_user(user.id, websocket)

    try:
        now = datetime.now(timezone.utc)
        await connection_manager.send_personal_message(
            websocket,
            {
                "type": "USER_CONNECTED",
                "version": 1,
                "timestamp": now.isoformat(),
                "user_id": str(user.id),
                "message": "Connected to real-time user stream",
            },
        )

        while True:
            _ = await websocket.receive_text()

    except WebSocketDisconnect:
        await connection_manager.disconnect_user(user.id, websocket)
    except Exception as e:
        logger.warning("WebSocket exception for user %s: %s", user.id, e)
        await connection_manager.disconnect_user(user.id, websocket)


@router.websocket("/hospital/{hospital_id}")
async def websocket_hospital_endpoint(
    websocket: WebSocket,
    hospital_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Staff hospital-level real-time WebSocket connection for live operations center metrics.

    Authentication: JWT via 'token' query param or 'Authorization: Bearer' header.
    Authorization: Staff must belong to the specified hospital (or be Admin).
    """
    user = authenticate_websocket_user(websocket, db)
    if not user:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="Unauthorized: Missing or invalid token")
        return

    from app.websocket.auth import authorize_staff_hospital
    authorized, reason = authorize_staff_hospital(db, user, hospital_id)
    if not authorized:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason=reason)
        return

    await connection_manager.connect_hospital(hospital_id, websocket)

    try:
        now = datetime.now(timezone.utc)
        await connection_manager.send_personal_message(
            websocket,
            {
                "type": "HOSPITAL_CONNECTED",
                "version": 1,
                "timestamp": now.isoformat(),
                "hospital_id": str(hospital_id),
                "message": "Connected to real-time hospital operations stream",
            },
        )

        while True:
            _ = await websocket.receive_text()

    except WebSocketDisconnect:
        await connection_manager.disconnect_hospital(hospital_id, websocket)
    except Exception as e:
        logger.warning("WebSocket exception for hospital %s: %s", hospital_id, e)
        await connection_manager.disconnect_hospital(hospital_id, websocket)

