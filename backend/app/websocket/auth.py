"""WebSocket authentication and authorization helpers."""

import logging
import uuid
from typing import Optional, Tuple
from fastapi import WebSocket, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.queue_entry import QueueEntry
from app.models.queue import Queue

logger = logging.getLogger(__name__)

# Close codes
WS_CLOSE_POLICY_VIOLATION = 1008
WS_CLOSE_UNAUTHORIZED = 1008


def extract_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Extract JWT token from Authorization header or 'token' query parameter.

    Security rule: Token values are NEVER logged.
    """
    # 1. Check query parameter '?token=...'
    token = websocket.query_params.get("token")
    if token and token.strip():
        return token.strip()

    # 2. Check Authorization header
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            return parts[1].strip()

    return None


def authenticate_websocket_user(websocket: WebSocket, db: Session) -> Optional[User]:
    """Authenticate WebSocket client from JWT token. Returns User or None."""
    token = extract_token_from_websocket(websocket)
    if not token:
        logger.warning("WebSocket authentication failed: No token provided")
        return None

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_uuid = uuid.UUID(user_id_str)
        user = db.query(User).filter(User.id == user_uuid).first()
        return user
    except Exception as e:
        logger.warning("WebSocket token validation failed: %s", type(e).__name__)
        return None


def authorize_patient_entry(
    db: Session,
    user: User,
    entry_id: uuid.UUID,
) -> Tuple[bool, Optional[QueueEntry], str]:
    """Authorize that user owns the target queue entry.

    Invariant: Patients can ONLY subscribe to their own queue entry.
    Staff and Admin can also subscribe for operational monitoring.
    """
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        return False, None, "Queue entry not found"

    # Patient role check: Strict ownership
    if user.role == UserRole.PATIENT:
        if entry.patient_user_id != user.id:
            logger.warning("Patient isolation violation: User %s attempted to subscribe to entry %s", user.id, entry_id)
            return False, entry, "Forbidden: Patient cannot access another patient's queue entry"

    return True, entry, "Authorized"


def authorize_staff_queue(
    db: Session,
    user: User,
    queue_id: uuid.UUID,
) -> Tuple[bool, Optional[Queue], str]:
    """Authorize that user is Staff/Admin for the target queue."""
    if user.role not in (UserRole.STAFF, UserRole.ADMIN):
        logger.warning("Queue subscription violation: Non-staff user %s attempted to monitor queue %s", user.id, queue_id)
        return False, None, "Forbidden: Only staff and admin can monitor full queues"

    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        return False, None, "Queue not found"

    return True, queue, "Authorized"


def authorize_staff_hospital(
    db: Session,
    user: User,
    hospital_id: uuid.UUID,
) -> Tuple[bool, str]:
    """Authorize that staff belongs to target hospital (or is admin)."""
    if user.role == UserRole.ADMIN:
        return True, "Authorized"

    if user.role != UserRole.STAFF:
        return False, "Forbidden: Only staff and admin can monitor hospital operations"

    if user.hospital_id != hospital_id:
        return False, "Forbidden: Staff cannot access other hospitals"

    return True, "Authorized"

