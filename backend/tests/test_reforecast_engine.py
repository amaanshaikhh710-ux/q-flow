"""Service tests for Dynamic Reforecasting, event triggers, explainability, meaningful shift threshold, and idempotency."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.services.reforecast_service import PredictionService, build_explanation
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from tests.conftest import make_test_user


def test_reforecast_on_emergency_insertion(db_session, seed_opd_data):
    """Verify emergency insertion shifts downstream patient later with emergency explanation."""
    queue = seed_opd_data["queue"]
    p_normal, _ = make_test_user(db_session, "Normal Waiting", "normwait@test.com", UserRole.PATIENT)
    p_emerg, _ = make_test_user(db_session, "Emergency Patient", "emgwait@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Emerg Ref", "sref@test.com", UserRole.STAFF)

    # Normal patient joins first
    e_norm = QueueEngineService.join_queue(db_session, queue.id, p_normal.id)
    pred_service = PredictionService()
    init_snap = pred_service.generate_initial_prediction(db_session, e_norm.id)
    assert init_snap is not None

    # Staff inserts emergency patient
    e_emerg, _ = QueueStateMachineService.insert_emergency(
        db_session, queue.id, p_emerg.id, staff.id, reason="Critical triage"
    )

    # Find the EMERGENCY_INSERTED event
    emerg_event = (
        db_session.query(QueueEvent)
        .filter(
            QueueEvent.queue_id == queue.id,
            QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value,
        )
        .first()
    )
    assert emerg_event is not None

    # Trigger reforecast
    reforecasted = pred_service.reforecast_after_event(db_session, queue.id, emerg_event.id)
    assert len(reforecasted) >= 1

    # Find e_norm's reforecasted snapshot
    norm_new_snap = next(s for s in reforecasted if s.queue_entry_id == e_norm.id)
    assert norm_new_snap.predicted_start_at > init_snap.predicted_start_at
    assert norm_new_snap.shift_minutes >= 10  # 15 min duration added ahead
    assert norm_new_snap.is_meaningful_change is True
    assert "emergency patient was inserted ahead of you" in norm_new_snap.explanation_text
    assert norm_new_snap.trigger_event_id == emerg_event.id


def test_reforecast_on_no_show(db_session, seed_opd_data):
    """Verify marking no-show moves downstream patient earlier with no-show explanation."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Pat Ahead", "ahead@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "Pat Behind", "behind@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff NS Ref", "snsref@test.com", UserRole.STAFF)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)

    pred_service = PredictionService()
    snap1 = pred_service.generate_initial_prediction(db_session, e1.id)
    snap2 = pred_service.generate_initial_prediction(db_session, e2.id)

    # e1 marked as no-show
    _, _ = QueueStateMachineService.mark_no_show(db_session, e1.id, staff.id, reason="Did not arrive")
    ns_event = (
        db_session.query(QueueEvent)
        .filter(
            QueueEvent.queue_entry_id == e1.id,
            QueueEvent.event_type == QueueEventType.PATIENT_NO_SHOW.value,
        )
        .first()
    )

    reforecasted = pred_service.reforecast_after_event(db_session, queue.id, ns_event.id)
    assert len(reforecasted) == 1
    new_snap2 = reforecasted[0]
    assert new_snap2.queue_entry_id == e2.id

    # e2 start time moves earlier
    assert new_snap2.predicted_start_at < snap2.predicted_start_at
    assert new_snap2.shift_minutes < 0
    assert "marked as a no-show" in new_snap2.explanation_text


def test_reforecast_on_doctor_delay(db_session, seed_opd_data):
    """Verify reporting doctor delay moves downstream predictions later with delay explanation."""
    queue = seed_opd_data["queue"]
    p, _ = make_test_user(db_session, "Delay Pat Ref", "delref@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Del Ref", "sdelref@test.com", UserRole.STAFF)

    entry = QueueEngineService.join_queue(db_session, queue.id, p.id)
    pred_service = PredictionService()
    init_snap = pred_service.generate_initial_prediction(db_session, entry.id)

    # Record 20-minute doctor delay
    delay_event = QueueStateMachineService.record_doctor_delay(
        db_session, queue.id, delay_minutes=20, actor_id=staff.id, reason="Traffic congestion"
    )

    reforecasted = pred_service.reforecast_after_event(db_session, queue.id, delay_event.id)
    assert len(reforecasted) == 1
    new_snap = reforecasted[0]

    assert new_snap.shift_minutes == 20
    assert new_snap.is_meaningful_change is True
    assert "doctor reported an operational delay" in new_snap.explanation_text


def test_meaningful_change_threshold_logic():
    """Verify >= 10 minute threshold marks changes as meaningful; < 10 minute is not."""
    # 5-minute shift (< 10)
    text_5, exp_5 = build_explanation(
        event_type=QueueEventType.CONSULTATION_COMPLETED.value,
        shift_minutes=5,
        is_meaningful=False,
        payload={},
    )
    assert exp_5["is_meaningful_change"] is False

    # 10-minute shift (>= 10)
    text_10, exp_10 = build_explanation(
        event_type=QueueEventType.EMERGENCY_INSERTED.value,
        shift_minutes=10,
        is_meaningful=True,
        payload={},
    )
    assert exp_10["is_meaningful_change"] is True

    # 15-minute shift (>= 10)
    text_15, exp_15 = build_explanation(
        event_type=QueueEventType.DOCTOR_DELAY.value,
        shift_minutes=15,
        is_meaningful=True,
        payload={},
    )
    assert exp_15["is_meaningful_change"] is True


def test_reforecast_idempotency(db_session, seed_opd_data):
    """Verify processing the same event twice returns existing snapshots without creating duplicates."""
    queue = seed_opd_data["queue"]
    p, _ = make_test_user(db_session, "Idempotent Pat", "idemppat@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Idemp", "sidemp@test.com", UserRole.STAFF)

    entry = QueueEngineService.join_queue(db_session, queue.id, p.id)
    pred_service = PredictionService()
    pred_service.generate_initial_prediction(db_session, entry.id)

    delay_event = QueueStateMachineService.record_doctor_delay(
        db_session, queue.id, delay_minutes=15, actor_id=staff.id, reason="Ward round"
    )

    # First call creates 1 new snapshot
    first_res = pred_service.reforecast_after_event(db_session, queue.id, delay_event.id)
    assert len(first_res) == 1
    snap_id = first_res[0].id

    # Total snapshots for entry is 2 (initial + delay)
    count_1 = db_session.query(PredictionSnapshot).filter(PredictionSnapshot.queue_entry_id == entry.id).count()
    assert count_1 == 2

    # Second call with same event_id must return existing snapshot without duplicating
    second_res = pred_service.reforecast_after_event(db_session, queue.id, delay_event.id)
    assert len(second_res) == 1
    assert second_res[0].id == snap_id

    count_2 = db_session.query(PredictionSnapshot).filter(PredictionSnapshot.queue_entry_id == entry.id).count()
    assert count_2 == 2
