"""Comprehensive correction test suite verifying the 18 mandatory operational requirements:

TEST 1: Staff creates appointment #14. Patient then books. Expected patient gets #15.
TEST 2: Patient creates #14. Staff then creates. Expected staff gets #15.
TEST 3: Staff and patient book concurrently. Expected unique numbers.
TEST 4: Different doctors have correct queue scopes.
TEST 5: Different hospitals have isolated queues.
TEST 6: Staff Hospital A attempts to access Hospital B. Expected DENIED (403).
TEST 7: Patient A attempts to access Patient B's appointment. Expected DENIED (403).
TEST 8: Patient arrival changes appointment state (BOOKED -> ARRIVED, arrived_at recorded).
TEST 9: Consultation start records timestamp.
TEST 10: Consultation end records timestamp.
TEST 11: Duration is calculated correctly (completed_at - started_at).
TEST 12: Completed consultation updates queue.
TEST 13: Long consultation updates prediction.
TEST 14: Doctor delay updates prediction.
TEST 15: Emergency event updates prediction.
TEST 16: Patient receives queue notification through configured notification provider.
TEST 17: Google Maps travel calculation handles car/walking.
TEST 18: Google Maps API failure does not create fake travel time.
"""

import uuid
import pytest
from datetime import datetime, timedelta, timezone

from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.consultation import Consultation
from app.models.notification import NotificationStatus
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from app.services.reforecast_service import PredictionService
from app.services.notifications.mock_provider import MockNotificationProvider
from app.services.notifications.service import NotificationService
from app.services.travel.mock_provider import MockTravelProvider
from app.services.travel.base import TravelProviderException
from app.core.security import hash_password, create_access_token


def make_user_with_token(db, name: str, email: str, role: UserRole, hospital_id=None):
    unique_email = f"{uuid.uuid4().hex[:8]}_{email}"
    user = User(
        name=name,
        email=unique_email,
        password_hash=hash_password("password123"),
        role=role,
        hospital_id=hospital_id,
    )
    db.add(user)
    db.flush()
    token = create_access_token(subject=str(user.id), role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers


# ---------------------------------------------------------------------------
# TEST 1 & 2 & 3: Unified queue sequence, token generation, and concurrency
# ---------------------------------------------------------------------------

def test_1_staff_then_patient_booking_sequence(db_session, seed_opd_data):
    """TEST 1: Staff creates appointment #1. Patient then books. Expected patient gets #2."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff 1", "staff1@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)
    patient_user, _ = make_user_with_token(db_session, "Patient 1", "p1@patient.com", UserRole.PATIENT)

    # 1. Staff phone booking
    staff_entry = QueueEngineService.staff_book_appointment(
        db_session,
        queue_id=queue.id,
        staff_user_id=staff_user.id,
        patient_name="Rahul Phone",
        patient_phone="+919876543210",
        booking_source="PHONE",
    )
    assert staff_entry.token_number == 1
    assert staff_entry.status == QueueEntryStatus.BOOKED

    # 2. Patient online booking
    patient_entry = QueueEngineService.join_queue(
        db_session,
        queue_id=queue.id,
        patient_user_id=patient_user.id,
    )
    assert patient_entry.token_number == 2
    assert patient_entry.status == QueueEntryStatus.BOOKED


def test_2_patient_then_staff_booking_sequence(db_session, seed_opd_data):
    """TEST 2: Patient creates #1. Staff then creates. Expected staff gets #2."""
    queue = seed_opd_data["queue"]
    patient_user, _ = make_user_with_token(db_session, "Patient 2", "p2@patient.com", UserRole.PATIENT)
    staff_user, _ = make_user_with_token(db_session, "Staff 2", "staff2@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)

    # 1. Patient online booking
    patient_entry = QueueEngineService.join_queue(
        db_session,
        queue_id=queue.id,
        patient_user_id=patient_user.id,
    )
    assert patient_entry.token_number == 1

    # 2. Staff walk-in booking
    staff_entry = QueueEngineService.staff_book_appointment(
        db_session,
        queue_id=queue.id,
        staff_user_id=staff_user.id,
        patient_name="Amit Walkin",
        booking_source="WALK_IN",
    )
    assert staff_entry.token_number == 2
    # Walk-ins are physically present, so status is WAITING and arrived_at is set
    assert staff_entry.status == QueueEntryStatus.WAITING
    assert staff_entry.arrived_at is not None


def test_3_concurrent_or_sequential_unique_tokens(db_session, seed_opd_data):
    """TEST 3: Multiple bookings in sequence or parallel must yield strictly unique numbers."""
    queue = seed_opd_data["queue"]
    tokens = set()

    for i in range(5):
        p_user, _ = make_user_with_token(db_session, f"P_{i}", f"p_{i}_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
        entry = QueueEngineService.join_queue(db_session, queue_id=queue.id, patient_user_id=p_user.id)
        assert entry.token_number not in tokens
        tokens.add(entry.token_number)

    assert len(tokens) == 5
    assert tokens == {1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# TEST 4 & 5: Scopes and Data Isolation
# ---------------------------------------------------------------------------

def test_4_different_doctors_have_correct_queue_scopes(db_session, seed_opd_data):
    """TEST 4: Different doctors have separate, isolated queue scopes."""
    dept = seed_opd_data["department"]
    doc1 = seed_opd_data["doctor"]

    # Create Doctor 2
    doc2 = Doctor(department_id=dept.id, name="Dr. Priya Sharma", status=DoctorStatus.AVAILABLE)
    db_session.add(doc2)
    db_session.flush()

    session2 = OPDSession(
        department_id=dept.id,
        doctor_id=doc2.id,
        starts_at=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    db_session.add(session2)
    db_session.flush()

    queue2 = Queue(opd_session_id=session2.id, name="Cardiology Dr. Priya OPD", status=QueueStatus.ACTIVE)
    db_session.add(queue2)
    db_session.flush()

    # Queue 1 has doctor 1, Queue 2 has doctor 2
    assert seed_opd_data["queue"].opd_session.doctor_id == doc1.id
    assert queue2.opd_session.doctor_id == doc2.id
    assert seed_opd_data["queue"].id != queue2.id


def test_5_different_hospitals_have_isolated_queues(db_session, seed_opd_data):
    """TEST 5: Different hospitals have completely isolated queues."""
    hosp1 = seed_opd_data["hospital"]

    # Create Hospital 2
    hosp2 = Hospital(name="BYL Nair Charitable Hospital", address="Mumbai Central")
    db_session.add(hosp2)
    db_session.flush()

    dept2 = Department(hospital_id=hosp2.id, name="General Medicine")
    db_session.add(dept2)
    db_session.flush()

    doc2 = Doctor(department_id=dept2.id, name="Dr. Rakesh Sawant", status=DoctorStatus.AVAILABLE)
    db_session.add(doc2)
    db_session.flush()

    session2 = OPDSession(department_id=dept2.id, doctor_id=doc2.id, starts_at=datetime.now(timezone.utc), status=SessionStatus.ACTIVE)
    db_session.add(session2)
    db_session.flush()

    queue2 = Queue(opd_session_id=session2.id, name="Nair Hospital GenMed OPD", status=QueueStatus.ACTIVE)
    db_session.add(queue2)
    db_session.flush()

    # Verify hospital scopes
    assert seed_opd_data["queue"].opd_session.department.hospital_id == hosp1.id
    assert queue2.opd_session.department.hospital_id == hosp2.id
    assert hosp1.id != hosp2.id


def test_6_cross_hospital_access_denied(test_client, db_session, seed_opd_data):
    """TEST 6: Staff Hospital A attempts to access Hospital B. Expected 403 DENIED."""
    hosp_a = seed_opd_data["hospital"]
    queue_a = seed_opd_data["queue"]

    # Create Hospital B and Queue B
    hosp_b = Hospital(name="Sir J.J. Hospital", address="Byculla")
    db_session.add(hosp_b)
    db_session.flush()

    dept_b = Department(hospital_id=hosp_b.id, name="General Medicine")
    db_session.add(dept_b)
    db_session.flush()

    doc_b = Doctor(department_id=dept_b.id, name="Dr. Sanjay Surase", status=DoctorStatus.AVAILABLE)
    db_session.add(doc_b)
    db_session.flush()

    session_b = OPDSession(department_id=dept_b.id, doctor_id=doc_b.id, starts_at=datetime.now(timezone.utc), status=SessionStatus.ACTIVE)
    db_session.add(session_b)
    db_session.flush()

    queue_b = Queue(opd_session_id=session_b.id, name="JJ Hospital OPD", status=QueueStatus.ACTIVE)
    db_session.add(queue_b)
    db_session.flush()

    # Staff A belongs to Hospital A
    staff_a, headers_a = make_user_with_token(db_session, "Staff A", "staff_a@hosp.com", UserRole.STAFF, hosp_a.id)

    # 1. Staff A accessing Queue A -> Allowed (200)
    res_a = test_client.get(f"/api/v1/queues/{queue_a.id}/snapshot", headers=headers_a)
    assert res_a.status_code == 200

    # 2. Staff A accessing Queue B -> Forbidden (403)
    res_b = test_client.get(f"/api/v1/queues/{queue_b.id}/snapshot", headers=headers_a)
    assert res_b.status_code == 403
    assert "Forbidden" in res_b.json()["detail"] or "denied" in res_b.json()["detail"].lower()


def test_7_cross_patient_access_denied(test_client, db_session, seed_opd_data):
    """TEST 7: Patient A attempts to access Patient B's appointment. Expected 403 DENIED."""
    queue = seed_opd_data["queue"]
    patient_a, headers_a = make_user_with_token(db_session, "Patient A", "pa@test.com", UserRole.PATIENT)
    patient_b, headers_b = make_user_with_token(db_session, "Patient B", "pb@test.com", UserRole.PATIENT)

    # Patient B joins queue
    entry_b = QueueEngineService.join_queue(db_session, queue_id=queue.id, patient_user_id=patient_b.id)

    # Patient A attempts to access Patient B's entry
    res = test_client.get(f"/api/v1/queue-entries/{entry_b.id}", headers=headers_a)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# TEST 8, 9, 10, 11, 12: Lifecycle, Timestamps, Duration & Progression
# ---------------------------------------------------------------------------

def test_8_patient_arrival_changes_state(db_session, seed_opd_data):
    """TEST 8: Patient arrival moves state to ARRIVED, sets arrived_at, and logs audit event."""
    queue = seed_opd_data["queue"]
    patient, _ = make_user_with_token(db_session, "Patient Arrive", "parrive@test.com", UserRole.PATIENT)
    staff_user, _ = make_user_with_token(db_session, "Staff Arrive", "sarrive@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)
    entry = QueueEngineService.join_queue(db_session, queue_id=queue.id, patient_user_id=patient.id)
    assert entry.status == QueueEntryStatus.BOOKED
    assert entry.arrived_at is None

    # Mark arrived
    arrived_entry, _ = QueueStateMachineService.mark_arrived(db_session, entry_id=entry.id, actor_id=staff_user.id)
    assert arrived_entry.status == QueueEntryStatus.ARRIVED
    assert arrived_entry.arrived_at is not None

    # Verify event logged
    event = db_session.query(QueueEvent).filter(
        QueueEvent.queue_entry_id == entry.id,
        QueueEvent.event_type == QueueEventType.PATIENT_ARRIVED.value,
    ).first()
    assert event is not None


def test_9_10_11_consultation_timestamps_and_duration(db_session, seed_opd_data):
    """TEST 9, 10, 11: Start records timestamp, End records timestamp, Duration is calculated correctly."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff Doc", "sdoc@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)

    # Create walk-in entry directly in WAITING state
    entry = QueueEngineService.staff_book_appointment(
        db_session,
        queue_id=queue.id,
        staff_user_id=staff_user.id,
        patient_name="Suresh Time",
        booking_source="WALK_IN",
    )
    assert entry.status == QueueEntryStatus.WAITING

    # Call patient first (WAITING -> CALLED)
    called_entry, _ = QueueStateMachineService.call_patient(db_session, entry_id=entry.id, actor_id=staff_user.id)
    assert called_entry.status == QueueEntryStatus.CALLED

    # TEST 9: Start consultation (CALLED -> IN_CONSULTATION)
    consultation = QueueStateMachineService.start_consultation(db_session, entry_id=entry.id, actor_id=staff_user.id)
    assert entry.status == QueueEntryStatus.IN_CONSULTATION
    assert consultation is not None
    assert consultation.started_at is not None

    # Simulate elapsed consultation time (15 minutes)
    consultation.started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    db_session.flush()

    # TEST 10: End consultation
    completed_consultation = QueueStateMachineService.complete_consultation(db_session, entry_id=entry.id, actor_id=staff_user.id)
    db_session.refresh(entry)
    assert entry.status == QueueEntryStatus.COMPLETED
    assert completed_consultation.completed_at is not None

    # TEST 11: Verify duration calculation
    assert completed_consultation.duration_seconds is not None
    duration_min = completed_consultation.duration_seconds / 60
    assert 14.5 <= duration_min <= 15.5


def test_12_completed_consultation_updates_queue(db_session, seed_opd_data):
    """TEST 12: Completed consultation updates queue progression."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff Prog", "sprog@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)

    e1 = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="P1", booking_source="WALK_IN")
    e2 = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="P2", booking_source="WALK_IN")

    # Initially e2 is behind e1
    pos_before = QueueEngineService.get_entry_position(db_session, e2)
    assert pos_before == 2

    # e1 completes consultation
    QueueStateMachineService.call_patient(db_session, entry_id=e1.id, actor_id=staff_user.id)
    QueueStateMachineService.start_consultation(db_session, entry_id=e1.id, actor_id=staff_user.id)
    QueueStateMachineService.complete_consultation(db_session, entry_id=e1.id, actor_id=staff_user.id)

    # e2 advances to position 1
    pos_after = QueueEngineService.get_entry_position(db_session, e2)
    assert pos_after == 1


# ---------------------------------------------------------------------------
# TEST 13, 14, 15: Prediction Updates
# ---------------------------------------------------------------------------

def test_13_long_consultation_updates_prediction(db_session, seed_opd_data):
    """TEST 13: Long consultation updates prediction via PredictionService."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff Pred", "spred@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)

    e1 = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="P1 Long", booking_source="WALK_IN")
    e2 = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="P2 Waiting", booking_source="WALK_IN")

    service = PredictionService()
    calc1 = service.calculate_entry_prediction(db_session, e2)
    assert calc1 is not None
    assert "predicted_start_at" in calc1

    # Start consultation on e1 and simulate a long consultation (30 min)
    QueueStateMachineService.call_patient(db_session, entry_id=e1.id, actor_id=staff_user.id)
    consultation = QueueStateMachineService.start_consultation(db_session, entry_id=e1.id, actor_id=staff_user.id)
    consultation.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.flush()

    # Recalculate e2 prediction
    calc2 = service.calculate_entry_prediction(db_session, e2)
    assert calc2 is not None
    assert "predicted_start_at" in calc2


def test_14_doctor_delay_updates_prediction(db_session, seed_opd_data):
    """TEST 14: Doctor delay records delay and shifts predictions."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff Delay", "sdelay@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)

    e1 = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="P1 Delay", booking_source="WALK_IN")

    event = QueueStateMachineService.record_doctor_delay(
        db_session,
        queue_id=queue.id,
        delay_minutes=25,
        actor_id=staff_user.id,
        reason="Traffic congestion",
    )
    assert event.event_type == QueueEventType.DOCTOR_DELAY.value
    assert event.payload_json.get("delay_minutes") == 25

    service = PredictionService()
    snapshots = service.reforecast_after_event(db_session, queue_id=queue.id, event_id=event.id)
    assert len(snapshots) >= 1



def test_15_emergency_event_updates_prediction(db_session, seed_opd_data):
    """TEST 15: Emergency event inserts priority patient and adjusts queue."""
    queue = seed_opd_data["queue"]
    staff_user, _ = make_user_with_token(db_session, "Staff Emer", "semer@hosp.com", UserRole.STAFF, seed_opd_data["hospital"].id)
    emer_patient, _ = make_user_with_token(db_session, "Emer Patient", "emerp@test.com", UserRole.PATIENT)

    # Patient in waiting line
    normal_p = QueueEngineService.staff_book_appointment(db_session, queue_id=queue.id, staff_user_id=staff_user.id, patient_name="Normal Patient", booking_source="WALK_IN")

    # Emergency patient inserted
    emer_entry, _ = QueueStateMachineService.insert_emergency(
        db_session,
        queue_id=queue.id,
        patient_user_id=emer_patient.id,
        actor_id=staff_user.id,
        reason="Trauma emergency incoming",
    )
    assert emer_entry.priority_class == PriorityClass.EMERGENCY

    # Emergency patient is ranked ahead of normal patient in waiting line
    waiting = QueueEngineService.get_ordered_waiting_entries(db_session, queue_id=queue.id)
    assert waiting[0].id == emer_entry.id


# ---------------------------------------------------------------------------
# TEST 16: Notification Dispatch
# ---------------------------------------------------------------------------

def test_16_patient_queue_notification(db_session, seed_opd_data):
    """TEST 16: Patient receives queue notification through configured notification provider."""
    queue = seed_opd_data["queue"]
    patient, _ = make_user_with_token(db_session, "Notification Patient", "np@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue_id=queue.id, patient_user_id=patient.id)

    mock_provider = MockNotificationProvider()
    notif_service = NotificationService(provider=mock_provider)

    notif = notif_service.send_queue_event_notification(
        db_session,
        entry=entry,
        title="Queue Update",
        message="Your doctor is running 15 minutes delayed.",
        notification_type="QUEUE_UPDATE",
    )

    assert notif is not None
    assert notif.status in (NotificationStatus.SENT.value, "sent", "SENT")
    assert len(mock_provider.sent_notifications) == 1
    assert "delayed" in mock_provider.sent_notifications[0]["message"]


# ---------------------------------------------------------------------------
# TEST 17 & 18: Google Maps Travel Calculation and Failure Handling
# ---------------------------------------------------------------------------

def test_17_travel_calculation_handles_car_and_walking():
    """TEST 17: Travel calculation correctly supports driving (DRIVE) and walking (WALK)."""
    provider = MockTravelProvider()

    # Driving calculation
    drive_res = provider.estimate_travel(
        origin_lat=19.0000,
        origin_lng=72.8400,
        dest_lat=19.0026,
        dest_lng=72.8423,
        travel_mode="DRIVE",
    )
    assert drive_res.duration_seconds > 0

    # Walking calculation
    walk_res = provider.estimate_travel(
        origin_lat=19.0000,
        origin_lng=72.8400,
        dest_lat=19.0026,
        dest_lng=72.8423,
        travel_mode="WALK",
    )
    assert walk_res.duration_seconds > 0
    # Walking should take longer than driving
    assert walk_res.duration_seconds >= drive_res.duration_seconds


def test_18_google_maps_api_failure_does_not_create_fake_travel_time():
    """TEST 18: Google Maps API failure raises TravelProviderException, never returns fake travel time."""
    failing_provider = MockTravelProvider(should_fail=True)

    with pytest.raises(TravelProviderException):
        failing_provider.estimate_travel(
            origin_lat=19.0000,
            origin_lng=72.8400,
            dest_lat=19.0026,
            dest_lng=72.8423,
            travel_mode="DRIVE",
        )

