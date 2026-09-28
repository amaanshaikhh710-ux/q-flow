"""Unit and service tests for QueueEngineService (token allocation, ordering, positions, snapshot)."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.queue_event import QueueEvent, QueueEventType
from app.services.queue_engine import QueueEngineService, format_token
from tests.conftest import make_test_user


def test_token_formatting():
    """Verify standard display token formatting."""
    assert format_token(1) == "Q001"
    assert format_token(42) == "Q042"
    assert format_token(999) == "Q999"
    assert format_token(1234) == "Q1234"


def test_atomic_queue_join_and_token_allocation(db_session, seed_opd_data):
    """Verify sequential, atomic token allocation upon patient join."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Patient One", "p1@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "Patient Two", "p2@test.com", UserRole.PATIENT)
    p3, _ = make_test_user(db_session, "Patient Three", "p3@test.com", UserRole.PATIENT)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    assert e1.token_number == 1
    assert e1.status == QueueEntryStatus.WAITING

    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)
    assert e2.token_number == 2
    assert e2.status == QueueEntryStatus.WAITING

    e3 = QueueEngineService.join_queue(db_session, queue.id, p3.id)
    assert e3.token_number == 3
    assert e3.status == QueueEntryStatus.WAITING

    # Verify audit events created for joins
    events = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_id == queue.id, QueueEvent.event_type == QueueEventType.PATIENT_JOINED.value)
        .all()
    )
    assert len(events) == 3


def test_duplicate_active_join_prevention(db_session, seed_opd_data):
    """Verify a patient cannot join a queue twice while having an active ticket."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Active Patient", "active@test.com", UserRole.PATIENT)

    QueueEngineService.join_queue(db_session, queue.id, p1.id)

    # Attempt second join
    with pytest.raises(HTTPException) as exc_info:
        QueueEngineService.join_queue(db_session, queue.id, p1.id)
    assert exc_info.value.status_code == 409
    assert "already has an active ticket" in exc_info.value.detail


def test_join_inactive_queue_rejected(db_session, seed_opd_data):
    """Verify joining a paused or completed queue returns 409 Conflict."""
    queue = seed_opd_data["queue"]
    queue.status = QueueStatus.PAUSED
    db_session.commit()

    p1, _ = make_test_user(db_session, "Late Patient", "late@test.com", UserRole.PATIENT)
    with pytest.raises(HTTPException) as exc_info:
        QueueEngineService.join_queue(db_session, queue.id, p1.id)
    assert exc_info.value.status_code == 409
    assert "currently paused" in exc_info.value.detail


def test_priority_ordering_and_deterministic_positions(db_session, seed_opd_data):
    """Verify EMERGENCY > PRIORITY > NORMAL queue ordering regardless of join time."""
    queue = seed_opd_data["queue"]
    p_norm, _ = make_test_user(db_session, "Normal Patient", "norm@test.com", UserRole.PATIENT)
    p_prio, _ = make_test_user(db_session, "Priority Patient", "prio@test.com", UserRole.PATIENT)
    p_emerg, _ = make_test_user(db_session, "Emergency Patient", "emerg@test.com", UserRole.PATIENT)

    # Normal patient joins first
    e_norm = QueueEngineService.join_queue(db_session, queue.id, p_norm.id, PriorityClass.NORMAL)
    # Priority patient joins second
    e_prio = QueueEngineService.join_queue(db_session, queue.id, p_prio.id, PriorityClass.PRIORITY)
    # Emergency patient joins third
    e_emerg = QueueEngineService.join_queue(db_session, queue.id, p_emerg.id, PriorityClass.EMERGENCY)

    ordered = QueueEngineService.get_ordered_waiting_entries(db_session, queue.id)
    assert [entry.id for entry in ordered] == [e_emerg.id, e_prio.id, e_norm.id]

    # Verify positions
    assert QueueEngineService.get_entry_position(db_session, e_emerg) == 1
    assert QueueEngineService.get_entry_position(db_session, e_prio) == 2
    assert QueueEngineService.get_entry_position(db_session, e_norm) == 3


def test_position_calculation_across_entry_statuses(db_session, seed_opd_data):
    """Verify position is 0 for called/serving and None for completed/no-show/left."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "Patient Status", "stat@test.com", UserRole.PATIENT)
    e = QueueEngineService.join_queue(db_session, queue.id, p1.id)

    assert QueueEngineService.get_entry_position(db_session, e) == 1

    e.status = QueueEntryStatus.CALLED
    db_session.commit()
    assert QueueEngineService.get_entry_position(db_session, e) == 0

    e.status = QueueEntryStatus.IN_CONSULTATION
    db_session.commit()
    assert QueueEngineService.get_entry_position(db_session, e) == 0

    for inactive_status in [
        QueueEntryStatus.COMPLETED,
        QueueEntryStatus.NO_SHOW,
        QueueEntryStatus.TEMPORARILY_LEFT,
        QueueEntryStatus.RETURNED,
    ]:
        e.status = inactive_status
        db_session.commit()
        assert QueueEngineService.get_entry_position(db_session, e) is None


def test_get_affected_downstream_entries(db_session, seed_opd_data):
    """Verify identifying affected waiting entries from a given rank position."""
    queue = seed_opd_data["queue"]
    patients = [
        make_test_user(db_session, f"Pat {i}", f"pat{i}@test.com", UserRole.PATIENT)[0]
        for i in range(5)
    ]
    entries = [
        QueueEngineService.join_queue(db_session, queue.id, p.id)
        for p in patients
    ]

    # Affected from position 3 (entries 3, 4, 5)
    affected_ids, affected_items = QueueEngineService.get_affected_downstream_entries(
        db_session, queue.id, from_position=3
    )
    assert len(affected_ids) == 3
    assert affected_ids == [entries[2].id, entries[3].id, entries[4].id]
    assert [item.position for item in affected_items] == [3, 4, 5]


def test_authoritative_queue_snapshot(db_session, seed_opd_data):
    """Verify queue snapshot includes serving, called, next, and correct aggregate counts."""
    queue = seed_opd_data["queue"]
    doctor = seed_opd_data["doctor"]
    dept = seed_opd_data["department"]

    p1, _ = make_test_user(db_session, "Pat Serving", "srv@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "Pat Called", "cld@test.com", UserRole.PATIENT)
    p3, _ = make_test_user(db_session, "Pat Waiting 1", "w1@test.com", UserRole.PATIENT)
    p4, _ = make_test_user(db_session, "Pat Waiting 2", "w2@test.com", UserRole.PATIENT)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    e1.status = QueueEntryStatus.IN_CONSULTATION

    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)
    e2.status = QueueEntryStatus.CALLED

    e3 = QueueEngineService.join_queue(db_session, queue.id, p3.id)
    e4 = QueueEngineService.join_queue(db_session, queue.id, p4.id)
    db_session.commit()

    snapshot = QueueEngineService.get_queue_snapshot(db_session, queue.id)
    assert snapshot["queue_id"] == queue.id
    assert snapshot["doctor_name"] == doctor.name
    assert snapshot["department_name"] == dept.name
    assert snapshot["currently_serving"].id == e1.id
    assert snapshot["currently_called"].id == e2.id
    assert snapshot["next_patient"].id == e3.id
    assert snapshot["total_waiting"] == 2
    assert snapshot["total_in_consultation"] == 1
    assert len(snapshot["waiting_entries"]) == 2


def test_concurrent_queue_joins(db_session):
    """Verify multiple simultaneous joins allocate unique tokens without race conditions (Real PostgreSQL Concurrency)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.core.database import SessionLocal
    from app.models.hospital import Hospital
    from app.models.department import Department
    from app.models.doctor import Doctor
    from app.models.opd_session import OPDSession, SessionStatus

    setup_session = SessionLocal()
    created_user_ids = []
    created_queue_id = None
    created_session_id = None
    created_doctor_id = None
    created_dept_id = None
    created_hosp_id = None

    try:
        # 1. Setup test entities in real committed transaction so worker threads can access them
        hosp = Hospital(name="Concurrent Test Hospital")
        setup_session.add(hosp)
        setup_session.flush()
        created_hosp_id = hosp.id

        dept = Department(hospital_id=hosp.id, name="Concurrent Dept")
        setup_session.add(dept)
        setup_session.flush()
        created_dept_id = dept.id

        doc = Doctor(department_id=dept.id, name="Concurrent Doc")
        setup_session.add(doc)
        setup_session.flush()
        created_doctor_id = doc.id

        sess = OPDSession(
            department_id=dept.id,
            doctor_id=doc.id,
            starts_at=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE,
        )
        setup_session.add(sess)
        setup_session.flush()
        created_session_id = sess.id

        q = Queue(opd_session_id=sess.id, name="Concurrent Queue", status=QueueStatus.ACTIVE)
        setup_session.add(q)
        setup_session.flush()
        created_queue_id = q.id

        # Ensure a DoctorSchedule exists for this doctor on today's date so joins are allowed
        from datetime import date, time
        from app.models.doctor_schedule import DoctorSchedule

        schedule = DoctorSchedule(
            hospital_id=hosp.id,
            department_id=dept.id,
            doctor_id=doc.id,
            schedule_date=date.today(),
            start_time=time(8, 0),
            end_time=time(18, 0),
            status="AVAILABLE",
            opd_session_id=sess.id,
        )
        setup_session.add(schedule)
        setup_session.flush()

        # Create 8 unique patients
        NUM_PATIENTS = 8
        patients = []
        for i in range(NUM_PATIENTS):
            u = User(
                name=f"Concurrent Patient {i}",
                email=f"concurrent_pat_{i}_{uuid.uuid4().hex[:6]}@test.com",
                password_hash="fakehash",
                role=UserRole.PATIENT,
            )
            setup_session.add(u)
            setup_session.flush()
            created_user_ids.append(u.id)
            patients.append(u.id)

            setup_session.commit()
    finally:
        setup_session.close()

    # 2. Execute concurrent joins from separate threads
    def join_worker(patient_id):
        worker_session = SessionLocal()
        try:
            entry = QueueEngineService.join_queue(
                db=worker_session,
                queue_id=str(created_queue_id),
                patient_user_id=patient_id,
            )
            return entry.token_number, entry.id
        finally:
            worker_session.close()

    results = []
    with ThreadPoolExecutor(max_workers=NUM_PATIENTS) as executor:
        futures = [executor.submit(join_worker, pid) for pid in patients]
        for f in as_completed(futures):
            results.append(f.result())

    # 3. Verify results
    assert len(results) == NUM_PATIENTS
    allocated_tokens = [r[0] for r in results]
    assert len(set(allocated_tokens)) == NUM_PATIENTS, "Duplicate token detected under concurrency!"
    assert sorted(allocated_tokens) == list(range(1, NUM_PATIENTS + 1))

    # 4. Verify in database and verify PATIENT_JOINED events
    verify_session = SessionLocal()
    try:
        entries = (
            verify_session.query(QueueEntry)
            .filter(QueueEntry.queue_id == created_queue_id)
            .order_by(QueueEntry.token_number.asc())
            .all()
        )
        assert len(entries) == NUM_PATIENTS
        assert [e.token_number for e in entries] == list(range(1, NUM_PATIENTS + 1))

        events = (
            verify_session.query(QueueEvent)
            .filter(
                QueueEvent.queue_id == created_queue_id,
                QueueEvent.event_type == QueueEventType.PATIENT_JOINED.value,
            )
            .all()
        )
        assert len(events) == NUM_PATIENTS
        entry_ids = {e.id for e in entries}
        event_entry_ids = {ev.queue_entry_id for ev in events}
        assert entry_ids == event_entry_ids
    finally:
        # Cleanup test entities
        verify_session.query(QueueEvent).filter(QueueEvent.queue_id == created_queue_id).delete()
        verify_session.query(QueueEntry).filter(QueueEntry.queue_id == created_queue_id).delete()
        verify_session.query(Queue).filter(Queue.id == created_queue_id).delete()
        verify_session.query(OPDSession).filter(OPDSession.id == created_session_id).delete()
        verify_session.query(Doctor).filter(Doctor.id == created_doctor_id).delete()
        verify_session.query(Department).filter(Department.id == created_dept_id).delete()
        verify_session.query(Hospital).filter(Hospital.id == created_hosp_id).delete()
        verify_session.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
        verify_session.commit()
        verify_session.close()
