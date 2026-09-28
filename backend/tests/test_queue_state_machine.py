"""Unit and service tests for QueueStateMachineService (lifecycle, transitions, events, disruptions)."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from tests.conftest import make_test_user


def test_valid_consultation_lifecycle(db_session, seed_opd_data):
    """Verify full linear lifecycle: WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED."""
    queue = seed_opd_data["queue"]
    doctor = seed_opd_data["doctor"]
    patient, _ = make_test_user(db_session, "Patient A", "pa@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff A", "sa@test.com", UserRole.STAFF)

    # 1. Join
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    assert entry.status == QueueEntryStatus.WAITING

    # 2. Call Next
    called_entry, affected_ids = QueueStateMachineService.call_next_patient(db_session, queue.id, staff.id)
    assert called_entry.id == entry.id
    assert called_entry.status == QueueEntryStatus.CALLED
    assert called_entry.called_at is not None

    # 3. Start Consultation -> Dedicated consultations table populated (DEC-031)
    consultation = QueueStateMachineService.start_consultation(db_session, entry.id, staff.id)
    assert entry.status == QueueEntryStatus.IN_CONSULTATION
    assert consultation.queue_entry_id == entry.id
    assert consultation.doctor_id == doctor.id
    assert consultation.started_at is not None
    assert consultation.completed_at is None

    # 4. Complete Consultation
    completed_consultation = QueueStateMachineService.complete_consultation(
        db_session, entry.id, staff.id, interruption_notes="Routine checkup, no issues"
    )
    assert entry.status == QueueEntryStatus.COMPLETED
    assert completed_consultation.completed_at is not None
    assert completed_consultation.duration_seconds is not None
    assert completed_consultation.duration_seconds >= 0
    assert completed_consultation.interruption_notes == "Routine checkup, no issues"

    # Verify audit events in event store
    events = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == entry.id)
        .order_by(QueueEvent.event_time.asc())
        .all()
    )
    event_types = [e.event_type for e in events]
    assert QueueEventType.PATIENT_JOINED.value in event_types
    assert QueueEventType.PATIENT_CALLED.value in event_types
    assert QueueEventType.CONSULTATION_STARTED.value in event_types
    assert QueueEventType.CONSULTATION_COMPLETED.value in event_types


def test_invalid_state_transitions_raise_409(db_session, seed_opd_data):
    """Verify invalid state machine transitions are strictly rejected with 409 Conflict."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Patient Invalid", "inv@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Invalid", "sinv@test.com", UserRole.STAFF)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    # WAITING -> COMPLETED is invalid (skips CALLED and IN_CONSULTATION)
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.complete_consultation(db_session, entry.id, staff.id)
    assert exc_info.value.status_code == 409
    assert "Invalid state transition" in exc_info.value.detail

    # WAITING -> IN_CONSULTATION is invalid (must be CALLED first)
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.start_consultation(db_session, entry.id, staff.id)
    assert exc_info.value.status_code == 409

    # Advance to COMPLETED
    QueueStateMachineService.call_patient(db_session, entry.id, staff.id)
    QueueStateMachineService.start_consultation(db_session, entry.id, staff.id)
    QueueStateMachineService.complete_consultation(db_session, entry.id, staff.id)

    # COMPLETED -> WAITING is invalid
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.validate_transition(entry.status, QueueEntryStatus.WAITING)
    assert exc_info.value.status_code == 409

    # COMPLETED -> NO_SHOW is invalid
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.mark_no_show(db_session, entry.id, staff.id)
    assert exc_info.value.status_code == 409


def test_call_next_on_empty_queue_raises_404(db_session, seed_opd_data):
    """Verify calling next on an empty queue returns 404 cleanly."""
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Empty", "sempty@test.com", UserRole.STAFF)

    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.call_next_patient(db_session, queue.id, staff.id)
    assert exc_info.value.status_code == 404
    assert "No eligible waiting patients" in exc_info.value.detail


def test_no_show_handling(db_session, seed_opd_data):
    """Verify marking no-show from WAITING and from CALLED states."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "NoShow 1", "ns1@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "NoShow 2", "ns2@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff NS", "sns@test.com", UserRole.STAFF)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)

    # No-show directly from WAITING
    e1_updated, _ = QueueStateMachineService.mark_no_show(db_session, e1.id, staff.id, reason="Did not arrive")
    assert e1_updated.status == QueueEntryStatus.NO_SHOW
    assert e1_updated.no_show_at is not None

    # No-show from CALLED
    QueueStateMachineService.call_patient(db_session, e2.id, staff.id)
    e2_updated, _ = QueueStateMachineService.mark_no_show(db_session, e2.id, staff.id, reason="Called 3 times, not at door")
    assert e2_updated.status == QueueEntryStatus.NO_SHOW

    # Verify event store records
    ns_events = (
        db_session.query(QueueEvent)
        .filter(
            QueueEvent.queue_id == queue.id,
            QueueEvent.event_type == QueueEventType.PATIENT_NO_SHOW.value,
        )
        .all()
    )
    assert len(ns_events) == 2


def test_temporary_leave_return_and_staff_requeue(db_session, seed_opd_data):
    """Verify DEC-033: WAITING -> TEMPORARILY_LEFT -> RETURNED -> STAFF_REQUEUES -> WAITING."""
    queue = seed_opd_data["queue"]
    p, _ = make_test_user(db_session, "Leave Patient", "lp@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Requeue", "srq@test.com", UserRole.STAFF)

    e = QueueEngineService.join_queue(db_session, queue.id, p.id)
    assert e.status == QueueEntryStatus.WAITING

    # 1. Patient leaves temporarily
    e_left, _ = QueueStateMachineService.temporary_leave(db_session, e.id, staff.id, reason="Gone to pharmacy")
    assert e_left.status == QueueEntryStatus.TEMPORARILY_LEFT
    assert e_left.temporary_left_at is not None

    # Cannot call a patient who has temporarily left
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.call_patient(db_session, e.id, staff.id)
    assert exc_info.value.status_code == 409

    # 2. Patient returns
    e_returned = QueueStateMachineService.return_patient(db_session, e.id, p.id)
    assert e_returned.status == QueueEntryStatus.RETURNED
    assert e_returned.returned_at is not None

    # Cannot call a patient who is RETURNED without staff re-queueing
    with pytest.raises(HTTPException) as exc_info:
        QueueStateMachineService.call_patient(db_session, e.id, staff.id)
    assert exc_info.value.status_code == 409

    # 3. Staff requeues patient back into active WAITING
    e_requeued, affected = QueueStateMachineService.requeue_patient(
        db_session, e.id, staff.id, priority_class=PriorityClass.NORMAL, reason="Staff restored patient"
    )
    assert e_requeued.status == QueueEntryStatus.WAITING

    # Patient is now eligible to be called
    e_called, _ = QueueStateMachineService.call_patient(db_session, e.id, staff.id)
    assert e_called.status == QueueEntryStatus.CALLED

    # Verify event trail
    events = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e.id)
        .all()
    )
    types = [ev.event_type for ev in events]
    assert QueueEventType.PATIENT_TEMPORARILY_LEFT.value in types
    assert QueueEventType.PATIENT_RETURNED.value in types
    assert QueueEventType.STAFF_REQUEUES.value in types


def test_priority_change_and_emergency_insertion(db_session, seed_opd_data):
    """Verify changing priority and staff emergency insertion without token renumbering."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "P1", "p1prio@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "P2", "p2prio@test.com", UserRole.PATIENT)
    p_emerg, _ = make_test_user(db_session, "Emergency Pat", "pemg@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Prio", "sprio@test.com", UserRole.STAFF)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)

    # Initial order: e1 (token 1), e2 (token 2)
    assert QueueEngineService.get_entry_position(db_session, e1) == 1
    assert QueueEngineService.get_entry_position(db_session, e2) == 2

    # Promote e2 to PRIORITY
    e2_promoted, affected = QueueStateMachineService.change_priority(
        db_session, e2.id, PriorityClass.PRIORITY, staff.id, reason="Elderly patient"
    )
    assert e2_promoted.priority_class == PriorityClass.PRIORITY
    assert e2_promoted.token_number == 2  # Identity unchanged!

    # Order inverted: e2 is now position 1, e1 is position 2
    assert QueueEngineService.get_entry_position(db_session, e2) == 1
    assert QueueEngineService.get_entry_position(db_session, e1) == 2

    # Insert emergency patient
    e_emerg, affected_emerg = QueueStateMachineService.insert_emergency(
        db_session, queue.id, p_emerg.id, staff.id, reason="Acute chest pain"
    )
    assert e_emerg.priority_class == PriorityClass.EMERGENCY
    assert e_emerg.token_number == 3  # Allocated next token number!

    # Emergency patient is position 1, e2 is position 2, e1 is position 3
    assert QueueEngineService.get_entry_position(db_session, e_emerg) == 1
    assert QueueEngineService.get_entry_position(db_session, e2) == 2
    assert QueueEngineService.get_entry_position(db_session, e1) == 3

    # Verify event naming semantics: PRIORITY_CHANGED for normal priority change, EMERGENCY_INSERTED for emergency
    events_e2 = db_session.query(QueueEvent).filter(QueueEvent.queue_entry_id == e2.id).all()
    assert any(ev.event_type == QueueEventType.PRIORITY_CHANGED.value for ev in events_e2)
    assert not any(ev.event_type == "PRIORITY_INSERTED" for ev in events_e2)

    events_emerg = db_session.query(QueueEvent).filter(QueueEvent.queue_entry_id == e_emerg.id).all()
    assert any(ev.event_type == QueueEventType.EMERGENCY_INSERTED.value for ev in events_emerg)


def test_operational_disruptions(db_session, seed_opd_data):
    """Verify doctor delay, doctor break, and queue pause/resume events."""
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Op", "sop@test.com", UserRole.STAFF)

    # Doctor delay
    delay_ev = QueueStateMachineService.record_doctor_delay(
        db_session, queue.id, delay_minutes=25, actor_id=staff.id, reason="Traffic delay"
    )
    assert delay_ev.event_type == QueueEventType.DOCTOR_DELAY.value
    assert delay_ev.payload_json["delay_minutes"] == 25

    # Doctor break start and end
    break_start_ev = QueueStateMachineService.record_doctor_break_start(
        db_session, queue.id, duration_minutes=15, actor_id=staff.id, reason="Tea break"
    )
    assert break_start_ev.event_type == QueueEventType.DOCTOR_BREAK_STARTED.value

    break_end_ev = QueueStateMachineService.record_doctor_break_end(
        db_session, queue.id, actor_id=staff.id
    )
    assert break_end_ev.event_type == QueueEventType.DOCTOR_BREAK_ENDED.value

    # Queue pause & resume
    q_paused = QueueStateMachineService.pause_queue(db_session, queue.id, staff.id)
    assert q_paused.status == QueueStatus.PAUSED

    # Pausing already paused queue raises 409
    with pytest.raises(HTTPException) as exc:
        QueueStateMachineService.pause_queue(db_session, queue.id, staff.id)
    assert exc.value.status_code == 409

    q_resumed = QueueStateMachineService.resume_queue(db_session, queue.id, staff.id)
    assert q_resumed.status == QueueStatus.ACTIVE


def test_event_immutability(db_session, seed_opd_data):
    """Verify historical queue_events are strictly immutable and never altered or deleted by normal mutations."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Immutability P1", "immut1@test.com", UserRole.PATIENT)
    p_emerg, _ = make_test_user(db_session, "Immutability Emerg", "immutemg@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Immutability Staff", "immutstaff@test.com", UserRole.STAFF)

    # Helper to snapshot an event
    def snapshot_event(event_id):
        ev = db_session.query(QueueEvent).filter(QueueEvent.id == event_id).one()
        return {
            "id": ev.id,
            "queue_id": ev.queue_id,
            "queue_entry_id": ev.queue_entry_id,
            "actor_user_id": ev.actor_user_id,
            "event_type": ev.event_type,
            "event_time": ev.event_time,
            "payload_json": dict(ev.payload_json),
        }

    # 1. Join
    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    ev_join = db_session.query(QueueEvent).filter(QueueEvent.queue_entry_id == e1.id).one()
    snap_join = snapshot_event(ev_join.id)

    # 2. Priority Change
    QueueStateMachineService.change_priority(db_session, e1.id, PriorityClass.PRIORITY, staff.id, reason="Priority upgrade")
    ev_prio = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e1.id, QueueEvent.event_type == QueueEventType.PRIORITY_CHANGED.value)
        .one()
    )
    snap_prio = snapshot_event(ev_prio.id)
    # Verify previous join event is unchanged
    assert snapshot_event(ev_join.id) == snap_join

    # 3. Emergency Insertion
    e_emerg, _ = QueueStateMachineService.insert_emergency(db_session, queue.id, p_emerg.id, staff.id, reason="Critical")
    ev_emerg = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e_emerg.id, QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value)
        .one()
    )
    snap_emerg = snapshot_event(ev_emerg.id)
    # Verify previous events are unchanged
    assert snapshot_event(ev_join.id) == snap_join
    assert snapshot_event(ev_prio.id) == snap_prio

    # 4. Call Patient
    QueueStateMachineService.call_patient(db_session, e1.id, staff.id)
    ev_call = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e1.id, QueueEvent.event_type == QueueEventType.PATIENT_CALLED.value)
        .one()
    )
    snap_call = snapshot_event(ev_call.id)
    # Verify previous events are unchanged
    assert snapshot_event(ev_join.id) == snap_join
    assert snapshot_event(ev_prio.id) == snap_prio
    assert snapshot_event(ev_emerg.id) == snap_emerg

    # 5. Start Consultation
    QueueStateMachineService.start_consultation(db_session, e1.id, staff.id)
    ev_start = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e1.id, QueueEvent.event_type == QueueEventType.CONSULTATION_STARTED.value)
        .one()
    )
    snap_start = snapshot_event(ev_start.id)
    # Verify previous events are unchanged
    assert snapshot_event(ev_join.id) == snap_join
    assert snapshot_event(ev_prio.id) == snap_prio
    assert snapshot_event(ev_emerg.id) == snap_emerg
    assert snapshot_event(ev_call.id) == snap_call

    # 6. Complete Consultation
    QueueStateMachineService.complete_consultation(db_session, e1.id, staff.id)
    ev_comp = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_entry_id == e1.id, QueueEvent.event_type == QueueEventType.CONSULTATION_COMPLETED.value)
        .one()
    )
    # Final check: all previous snapshots remain identical
    assert snapshot_event(ev_join.id) == snap_join
    assert snapshot_event(ev_prio.id) == snap_prio
    assert snapshot_event(ev_emerg.id) == snap_emerg
    assert snapshot_event(ev_call.id) == snap_call
    assert snapshot_event(ev_start.id) == snap_start

    # Verify all 7 events are preserved in append-only table (including PATIENT_JOINED for emergency patient)
    all_events = db_session.query(QueueEvent).filter(QueueEvent.queue_id == queue.id).all()
    assert len(all_events) == 7


def test_invalid_state_transitions_comprehensive(db_session, seed_opd_data):
    """Explicitly verify rejection of specified invalid transitions with HTTP 409 Conflict:
    1. COMPLETED -> WAITING
    2. COMPLETED -> CALLED
    3. COMPLETED -> NO_SHOW
    4. NO_SHOW -> IN_CONSULTATION
    5. WAITING -> COMPLETED
    """
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Pat Trans 1", "ptrans1@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "Pat Trans 2", "ptrans2@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Trans", "strans@test.com", UserRole.STAFF)

    # Entry 1 will be moved through lifecycle to COMPLETED
    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)

    # 5. WAITING -> COMPLETED (INVALID)
    with pytest.raises(HTTPException) as exc_5:
        QueueStateMachineService.complete_consultation(db_session, e1.id, staff.id)
    assert exc_5.value.status_code == 409
    assert "Cannot transition entry from 'WAITING' to 'COMPLETED'" in exc_5.value.detail

    # Advance e1 to COMPLETED
    QueueStateMachineService.call_patient(db_session, e1.id, staff.id)
    QueueStateMachineService.start_consultation(db_session, e1.id, staff.id)
    QueueStateMachineService.complete_consultation(db_session, e1.id, staff.id)
    assert e1.status == QueueEntryStatus.COMPLETED

    # 1. COMPLETED -> WAITING (INVALID)
    with pytest.raises(HTTPException) as exc_1:
        QueueStateMachineService.validate_transition(QueueEntryStatus.COMPLETED, QueueEntryStatus.WAITING)
    assert exc_1.value.status_code == 409
    assert "Cannot transition entry from 'COMPLETED' to 'WAITING'" in exc_1.value.detail

    # 2. COMPLETED -> CALLED (INVALID)
    with pytest.raises(HTTPException) as exc_2:
        QueueStateMachineService.call_patient(db_session, e1.id, staff.id)
    assert exc_2.value.status_code == 409
    assert "Cannot transition entry from 'COMPLETED' to 'CALLED'" in exc_2.value.detail

    # 3. COMPLETED -> NO_SHOW (INVALID)
    with pytest.raises(HTTPException) as exc_3:
        QueueStateMachineService.mark_no_show(db_session, e1.id, staff.id)
    assert exc_3.value.status_code == 409
    assert "Cannot transition entry from 'COMPLETED' to 'NO_SHOW'" in exc_3.value.detail

    # Entry 2 will be marked NO_SHOW
    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)
    QueueStateMachineService.mark_no_show(db_session, e2.id, staff.id)
    assert e2.status == QueueEntryStatus.NO_SHOW

    # 4. NO_SHOW -> IN_CONSULTATION (INVALID)
    with pytest.raises(HTTPException) as exc_4:
        QueueStateMachineService.start_consultation(db_session, e2.id, staff.id)
    assert exc_4.value.status_code == 409
    assert "Cannot transition entry from 'NO_SHOW' to 'IN_CONSULTATION'" in exc_4.value.detail
