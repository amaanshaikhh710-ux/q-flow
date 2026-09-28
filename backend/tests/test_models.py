"""Tests for models, relationships, constraints, and consultation normalization (DEC-031)."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import (
    Base,
    Hospital,
    Department,
    User,
    UserRole,
    Doctor,
    DoctorStatus,
    OPDSession,
    SessionStatus,
    Queue,
    QueueStatus,
    QueueEntry,
    PriorityClass,
    QueueEntryStatus,
    Consultation,
    QueueEvent,
    QueueEventType,
    Notification,
    NotificationChannel,
    NotificationStatus,
)


def test_model_metadata_table_count():
    """Verify all Q-FLOW tables are registered in Base metadata (including Phase 4 prediction_snapshots)."""
    expected_tables = {
        "hospitals",
        "departments",
        "users",
        "doctors",
        "opd_sessions",
        "queues",
        "queue_entries",
        "consultations",
        "queue_events",
        "notifications",
        "prediction_snapshots",
        "arrival_plans",
        "otp_tokens",
        "doctor_schedules",
        "doctor_availability",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables == actual_tables



def test_full_entity_hierarchy_and_relationships(db_session):
    """Verify complete CRUD lifecycle and foreign key relationships across all 10 tables."""
    now = datetime.now(timezone.utc)

    # 1. Hospital
    hospital = Hospital(name="Apex General Hospital", address="123 Health Ave, Bangalore")
    db_session.add(hospital)
    db_session.flush()
    assert hospital.id is not None

    # 2. Department
    department = Department(hospital_id=hospital.id, name="Cardiology")
    db_session.add(department)
    db_session.flush()
    assert department.hospital.name == "Apex General Hospital"

    # 3. Doctor
    doctor = Doctor(department_id=department.id, name="Dr. Priya Sharma", status=DoctorStatus.AVAILABLE)
    db_session.add(doctor)
    db_session.flush()
    assert doctor.department.name == "Cardiology"

    # 4. User (Patient & Staff)
    p_suffix = uuid.uuid4().hex[:6]
    patient = User(
        name="Rahul Verma",
        phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
        email=f"rahul_{p_suffix}@example.com",
        password_hash="hashed_pw_test",
        role=UserRole.PATIENT,
    )
    staff = User(
        name="Receptionist Maya",
        phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
        email=f"maya_{p_suffix}@apex.com",
        password_hash="hashed_pw_test",
        role=UserRole.STAFF,
    )
    db_session.add_all([patient, staff])
    db_session.flush()

    # 5. OPD Session
    session = OPDSession(
        department_id=department.id,
        doctor_id=doctor.id,
        starts_at=now,
        status=SessionStatus.ACTIVE,
    )
    db_session.add(session)
    db_session.flush()

    # 6. Queue
    queue = Queue(opd_session_id=session.id, name="Cardio Morning Queue", status=QueueStatus.ACTIVE)
    db_session.add(queue)
    db_session.flush()

    # 7. Queue Entry
    entry = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=1,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.WAITING,
        joined_at=now,
    )
    db_session.add(entry)
    db_session.flush()

    # 8. Consultation (Dedicated Normalized Table - DEC-031)
    consultation = Consultation(
        queue_entry_id=entry.id,
        doctor_id=doctor.id,
        started_at=now,
        completed_at=now,
        duration_seconds=720,  # 12 minutes
        interruption_notes="None",
    )
    db_session.add(consultation)
    db_session.flush()

    # Verify Consultation 1-to-1 relationship with QueueEntry
    assert entry.consultation is not None
    assert entry.consultation.duration_seconds == 720
    assert entry.consultation.doctor.name == "Dr. Priya Sharma"

    # 9. Queue Event (Append-only with JSONB)
    event = QueueEvent(
        queue_id=queue.id,
        queue_entry_id=entry.id,
        actor_user_id=staff.id,
        event_type=QueueEventType.PATIENT_JOINED.value,
        event_time=now,
        payload_json={"token": 1, "source": "web_pwa", "priority": "normal"},
    )
    db_session.add(event)
    db_session.flush()

    assert event.id is not None
    assert event.payload_json["token"] == 1
    assert event.actor.name == "Receptionist Maya"

    # 10. Notification
    notification = Notification(
        user_id=patient.id,
        queue_entry_id=entry.id,
        channel=NotificationChannel.SMS.value,
        notification_type="QUEUE_JOINED",
        content_reference="Token #1 confirmed",
        status=NotificationStatus.SENT.value,
    )
    db_session.add(notification)
    db_session.flush()

    assert notification.id is not None
    assert notification.user.name == "Rahul Verma"


def test_unique_token_number_constraint(db_session):
    """Verify unique constraint on (queue_id, token_number)."""
    now = datetime.now(timezone.utc)

    hospital = Hospital(name="Metro Hospital")
    db_session.add(hospital)
    db_session.flush()

    department = Department(hospital_id=hospital.id, name="General Medicine")
    db_session.add(department)
    db_session.flush()

    doctor = Doctor(department_id=department.id, name="Dr. Khan")
    db_session.add(doctor)
    db_session.flush()

    u_suffix = uuid.uuid4().hex[:6]
    user1 = User(name="User 1", email=f"u1_{u_suffix}@test.com", password_hash="pw1", role=UserRole.PATIENT)
    user2 = User(name="User 2", email=f"u2_{u_suffix}@test.com", password_hash="pw2", role=UserRole.PATIENT)
    db_session.add_all([user1, user2])
    db_session.flush()

    session = OPDSession(department_id=department.id, doctor_id=doctor.id, starts_at=now)
    db_session.add(session)
    db_session.flush()

    queue = Queue(opd_session_id=session.id, name="Main")
    db_session.add(queue)
    db_session.flush()

    entry1 = QueueEntry(queue_id=queue.id, patient_user_id=user1.id, token_number=42, joined_at=now)
    db_session.add(entry1)
    db_session.flush()

    # Attempt to insert duplicate token_number 42 in the same queue
    entry2 = QueueEntry(queue_id=queue.id, patient_user_id=user2.id, token_number=42, joined_at=now)
    db_session.add(entry2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_consultation_normalized_uniqueness(db_session):
    """Verify that each queue entry can only have at most one consultation record (1-to-1)."""
    now = datetime.now(timezone.utc)

    hospital = Hospital(name="Care Clinic")
    db_session.add(hospital)
    db_session.flush()

    department = Department(hospital_id=hospital.id, name="Pediatrics")
    db_session.add(department)
    db_session.flush()

    doctor = Doctor(department_id=department.id, name="Dr. Mehta")
    db_session.add(doctor)
    db_session.flush()

    k_suffix = uuid.uuid4().hex[:6]
    user = User(name="Kiddo", email=f"kid_{k_suffix}@test.com", password_hash="pw", role=UserRole.PATIENT)
    db_session.add(user)
    db_session.flush()

    session = OPDSession(department_id=department.id, doctor_id=doctor.id, starts_at=now)
    db_session.add(session)
    db_session.flush()

    queue = Queue(opd_session_id=session.id, name="Main")
    db_session.add(queue)
    db_session.flush()

    entry = QueueEntry(queue_id=queue.id, patient_user_id=user.id, token_number=10, joined_at=now)
    db_session.add(entry)
    db_session.flush()

    cons1 = Consultation(queue_entry_id=entry.id, doctor_id=doctor.id, started_at=now)
    db_session.add(cons1)
    db_session.flush()

    # Attempt to insert a second consultation for the same queue_entry_id
    cons2 = Consultation(queue_entry_id=entry.id, doctor_id=doctor.id, started_at=now)
    db_session.add(cons2)
    with pytest.raises(IntegrityError):
        db_session.flush()
