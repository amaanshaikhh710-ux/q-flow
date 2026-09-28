"""Tests for Phase 6 WebSocket updates and connections.

Covers:
- Requirement 22: Patient-specific WebSocket endpoint with JWT auth and strict isolation.
- Requirement 22: Staff-authorized queue-level WebSocket endpoint.
- Reconnection snapshot support.
- ConnectionManager add/remove/cleanup and safe broadcast.
- Zero PII leaks, zero origin coordinate leaks in snapshots.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest

from app.models.user import UserRole
from app.models.queue_event import QueueEventType
from app.models.queue_entry import QueueEntry
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.core.security import create_access_token
from app.services.queue_engine import QueueEngineService
from app.websocket.manager import ConnectionManager
from tests.conftest import make_test_user


def test_patient_ws_unauthenticated_rejected(test_client, seed_opd_data):
    """Connecting to patient WS without token must be rejected with 1008 / error."""
    entry_id = uuid.uuid4()
    with pytest.raises(Exception):
        with test_client.websocket_connect(f"/api/v1/ws/patient/{entry_id}") as ws:
            pass


def test_patient_ws_invalid_token_rejected(test_client, seed_opd_data):
    """Connecting to patient WS with invalid token must be rejected."""
    entry_id = uuid.uuid4()
    with pytest.raises(Exception):
        with test_client.websocket_connect(f"/api/v1/ws/patient/{entry_id}?token=invalid-jwt-token") as ws:
            pass


def test_patient_ws_isolation_patient_b_rejected_from_patient_a_entry(test_client, db_session, seed_opd_data):
    """Strict Patient Isolation: Patient B cannot connect to Patient A's entry."""
    queue = seed_opd_data["queue"]
    pat_a, _ = make_test_user(db_session, "WS Pat A", "wspata@test.com", UserRole.PATIENT)
    pat_b, _ = make_test_user(db_session, "WS Pat B", "wspatb@test.com", UserRole.PATIENT)

    entry_a = QueueEngineService.join_queue(db_session, queue.id, pat_a.id)

    token_b = create_access_token(pat_b.id, pat_b.role)

    # Connecting Patient B to entry A must fail
    with pytest.raises(Exception):
        with test_client.websocket_connect(f"/api/v1/ws/patient/{entry_a.id}?token={token_b}") as ws:
            pass


def test_patient_ws_connect_receives_initial_connected_and_snapshot(test_client, db_session, seed_opd_data):
    """Patient connecting to their own entry receives initial QUEUE_CONNECTED then QUEUE_SNAPSHOT."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "WS Pat Success", "wspatsuccess@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    token = create_access_token(patient.id, patient.role)

    with test_client.websocket_connect(f"/api/v1/ws/patient/{entry.id}?token={token}") as ws:
        # Message 1: QUEUE_CONNECTED
        msg1 = ws.receive_json()
        assert msg1["type"] == "QUEUE_CONNECTED"
        assert msg1["entry_id"] == str(entry.id)

        # Message 2: QUEUE_SNAPSHOT
        msg2 = ws.receive_json()
        assert msg2["type"] == "QUEUE_SNAPSHOT"
        assert msg2["entry_id"] == str(entry.id)
        assert msg2["token_display"] == f"Q{entry.token_number:03d}"
        assert msg2["patient_status"] == "WAITING"
        # Zero coordinate leaks
        assert "origin_latitude" not in str(msg2)
        assert "origin_longitude" not in str(msg2)


def test_patient_ws_reconnect_receives_latest_snapshot_with_prediction_and_arrival(test_client, db_session, seed_opd_data):
    """Reconnecting to patient WS receives the latest snapshot with prediction and arrival plan."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "WS Reconnect", "wsreconn@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=45),
        predicted_end_at=now + timedelta(minutes=65),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        is_meaningful_change=False,
        shift_minutes=0,
        explanation_text="Standard pace",
    )
    db_session.add(snapshot)
    db_session.commit()

    plan = ArrivalPlan(
        queue_entry_id=entry.id,
        prediction_snapshot_id=snapshot.id,
        consultation_start_at=now + timedelta(minutes=45),
        consultation_end_at=now + timedelta(minutes=65),
        arrival_start_at=now + timedelta(minutes=30),
        arrival_end_at=now + timedelta(minutes=40),
        departure_start_at=now + timedelta(minutes=10),
        departure_end_at=now + timedelta(minutes=20),
        travel_duration_seconds=1200,
        travel_uncertainty_seconds=300,
        arrival_buffer_seconds=600,
        travel_provider="mock",
        travel_status="OPTIMIZED",
    )
    db_session.add(plan)
    db_session.commit()

    token = create_access_token(patient.id, patient.role)

    with test_client.websocket_connect(f"/api/v1/ws/patient/{entry.id}?token={token}") as ws:
        _ = ws.receive_json()  # QUEUE_CONNECTED
        snap = ws.receive_json()  # QUEUE_SNAPSHOT
        assert snap["type"] == "QUEUE_SNAPSHOT"
        assert snap["prediction"] is not None
        assert snap["prediction"]["uncertainty_seconds"] == 300
        assert snap["arrival_plan"] is not None
        assert snap["arrival_plan"]["travel_status"] == "OPTIMIZED"
        assert "origin_latitude" not in str(snap)


def test_staff_ws_connect_to_queue(test_client, db_session, seed_opd_data):
    """Staff/Admin connecting to queue WS successfully connects and receives snapshot."""
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "WS Staff User", "wsstaff@test.com", UserRole.STAFF)

    token = create_access_token(staff.id, staff.role)

    with test_client.websocket_connect(f"/api/v1/ws/queue/{queue.id}?token={token}") as ws:
        msg1 = ws.receive_json()  # QUEUE_CONNECTED
        assert msg1["type"] == "QUEUE_CONNECTED"
        assert msg1["queue_id"] == str(queue.id)

        msg2 = ws.receive_json()  # QUEUE_SNAPSHOT
        assert msg2["type"] == "QUEUE_SNAPSHOT"
        assert msg2["payload"]["queue_id"] == str(queue.id)
        assert "waiting_count" in msg2["payload"]


def test_staff_ws_patient_role_rejected_from_queue_ws(test_client, db_session, seed_opd_data):
    """Patients must NOT be allowed to connect to the staff queue WS endpoint."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "WS Queue Pat", "wsqueuepat@test.com", UserRole.PATIENT)

    token = create_access_token(patient.id, patient.role)

    with pytest.raises(Exception):
        with test_client.websocket_connect(f"/api/v1/ws/queue/{queue.id}?token={token}") as ws:
            pass


def test_staff_can_view_patient_ws(test_client, db_session, seed_opd_data):
    """Staff is authorized to view a patient's ticket snapshot."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "WS Pat Ticket", "wspattick@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "WS Staff Inspector", "wsstaffinsp@test.com", UserRole.STAFF)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    token = create_access_token(staff.id, staff.role)

    with test_client.websocket_connect(f"/api/v1/ws/patient/{entry.id}?token={token}") as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "QUEUE_CONNECTED"
        msg2 = ws.receive_json()
        assert msg2["type"] == "QUEUE_SNAPSHOT"
        assert msg2["entry_id"] == str(entry.id)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_connection_manager_lifecycle():
    """Verify ConnectionManager connection tracking and stale cleanup."""
    manager = ConnectionManager()

    entry_id_1 = uuid.uuid4()
    entry_id_2 = uuid.uuid4()
    queue_id = uuid.uuid4()

    assert manager.get_patient_connection_count(entry_id_1) == 0

    class DummyWS:
        def __init__(self):
            self.closed = False
            self.messages = []

        async def accept(self):
            pass

        async def send_json(self, data: dict):
            if self.closed:
                raise RuntimeError("Connection closed")
            self.messages.append(data)

    ws1 = DummyWS()
    ws2 = DummyWS()
    ws_q = DummyWS()

    await manager.connect_patient(entry_id_1, ws1)
    await manager.connect_patient(entry_id_1, ws2)
    await manager.connect_queue(queue_id, ws_q)

    assert manager.get_patient_connection_count(entry_id_1) == 2
    assert manager.get_patient_connection_count(entry_id_2) == 0

    # Broadcast to patient
    msg = {"type": "QUEUE_REFORECAST", "message": "Test update"}
    await manager.send_to_patient(entry_id_1, msg)
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1

    # Simulate client disconnect
    ws1.closed = True
    await manager.send_to_patient(entry_id_1, msg)
    # Stale ws1 cleaned up automatically
    assert manager.get_patient_connection_count(entry_id_1) == 1

    # Explicit disconnect
    await manager.disconnect_patient(entry_id_1, ws2)
    assert manager.get_patient_connection_count(entry_id_1) == 0

    # Queue message
    await manager.broadcast_to_queue(queue_id, msg)
    assert len(ws_q.messages) == 1
    await manager.disconnect_queue(queue_id, ws_q)
