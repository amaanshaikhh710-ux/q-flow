"""Test suite for unified appointment system, token safety, staff authorization, and travel handling.

Tests required by the Q-FLOW specification:
1. Staff booking followed by patient booking (sequential token numbering)
2. Patient booking followed by staff booking (sequential token numbering)
3. Concurrent booking sequence safety (no duplicate token numbers)
4. Different doctors / queues isolation
5. Different hospitals isolation
6. Cross-hospital staff access denial (HTTP 403)
7. Patient access to only their own appointments (GET /my and cross-access 403)
8. Google Maps / API failure handling (no fabricated numbers, honest degradation)
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.services.queue_engine import QueueEngineService
from app.core.security import hash_password, create_access_token


def create_user_with_token(db, name: str, email: str, role: UserRole, hospital_id: str | None = None) -> tuple[User, dict]:
    """Helper to create a user and return (User, headers_dict)."""
    user = User(
        name=name,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        hospital_id=hospital_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers


def create_test_hospital_hierarchy(db, hospital_name: str):
    """Create a complete hospital hierarchy: hospital, department, doctor, session, queue."""
    hospital = Hospital(name=hospital_name, address="Test Address")
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    dept = Department(hospital_id=hospital.id, name="General Medicine")
    db.add(dept)
    db.commit()
    db.refresh(dept)

    doctor = Doctor(department_id=dept.id, name="Dr. Test Specialist", status=DoctorStatus.AVAILABLE)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    session = OPDSession(
        department_id=dept.id,
        doctor_id=doctor.id,
        starts_at=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    queue = Queue(
        opd_session_id=session.id,
        name=f"{hospital_name} OPD Queue",
        status=QueueStatus.ACTIVE,
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)

    # Ensure an authoritative DoctorSchedule exists for the doctor on today's date
    from datetime import date, time
    from app.models.doctor_schedule import DoctorSchedule

    sched = DoctorSchedule(
        hospital_id=hospital.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        schedule_date=date.today(),
        start_time=time(8, 0),
        end_time=time(18, 0),
        status="AVAILABLE",
        opd_session_id=session.id,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)

    return hospital, dept, doctor, session, queue


# 1. Staff booking followed by patient booking
def test_staff_booking_followed_by_patient_booking(test_client: TestClient, db_session):
    hospital, dept, doctor, session, queue = create_test_hospital_hierarchy(db_session, "City Care Hospital")
    staff_user, staff_headers = create_user_with_token(
        db_session, "Staff Member", f"staff_{uuid.uuid4().hex[:6]}@test.com", UserRole.STAFF, hospital.id
    )
    patient_user, patient_headers = create_user_with_token(
        db_session, "Online Patient", f"patient_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT
    )

    # 1. Staff books walk-in patient
    staff_resp = test_client.post(
        f"/api/v1/queues/{queue.id}/staff-book",
        json={
            "patient_name": "Walkin John",
            "patient_phone": "+919876543210",
            "booking_source": "WALK_IN",
            "priority": "NORMAL",
            "notes": "Walk-in registration",
        },
        headers=staff_headers,
    )
    assert staff_resp.status_code == 201, staff_resp.text
    staff_entry = staff_resp.json()["entry"]
    assert staff_entry["token_number"] == 1
    assert staff_entry["booking_source"] == "WALK_IN"

    # 2. Patient books online
    patient_resp = test_client.post(
        f"/api/v1/queues/{queue.id}/join",
        json={"priority": "NORMAL"},
        headers=patient_headers,
    )
    assert patient_resp.status_code == 201, patient_resp.text
    patient_entry = patient_resp.json()["entry"]
    assert patient_entry["token_number"] == 2
    assert patient_entry["booking_source"] == "ONLINE"


# 2. Patient booking followed by staff booking
def test_patient_booking_followed_by_staff_booking(test_client: TestClient, db_session):
    hospital, dept, doctor, session, queue = create_test_hospital_hierarchy(db_session, "Metro Clinic")
    staff_user, staff_headers = create_user_with_token(
        db_session, "Staff Member 2", f"staff_{uuid.uuid4().hex[:6]}@test.com", UserRole.STAFF, hospital.id
    )
    patient_user, patient_headers = create_user_with_token(
        db_session, "Online Patient 2", f"patient_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT
    )

    # 1. Patient books online
    patient_resp = test_client.post(
        f"/api/v1/queues/{queue.id}/join",
        json={"priority": "NORMAL"},
        headers=patient_headers,
    )
    assert patient_resp.status_code == 201, patient_resp.text
    patient_entry = patient_resp.json()["entry"]
    assert patient_entry["token_number"] == 1

    # 2. Staff books phone patient
    staff_resp = test_client.post(
        f"/api/v1/queues/{queue.id}/staff-book",
        json={
            "patient_name": "Phone Patient Alice",
            "patient_phone": "+919876500000",
            "booking_source": "PHONE",
            "priority": "NORMAL",
            "notes": "Telephonic booking",
        },
        headers=staff_headers,
    )
    assert staff_resp.status_code == 201, staff_resp.text
    staff_entry = staff_resp.json()["entry"]
    assert staff_entry["token_number"] == 2
    assert staff_entry["booking_source"] == "PHONE"


# 3. Concurrent booking sequence safety (mixed staff and patient bookings)
def test_concurrent_booking_sequence(db_session):
    setup_db = db_session
    hospital, dept, doctor, session, queue = create_test_hospital_hierarchy(setup_db, "Concurrency Clinic")
    staff_user, _ = create_user_with_token(
        setup_db, "Staff Concurrency", f"staff_{uuid.uuid4().hex[:6]}@test.com", UserRole.STAFF, hospital.id
    )

    patient_ids = []
    for i in range(4):
        p, _ = create_user_with_token(setup_db, f"Concurrent Pat {i}", f"pat_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
        patient_ids.append(p.id)

    queue_id = queue.id
    staff_id = staff_user.id
    setup_db.commit()

    def worker_patient(patient_id):
        worker_db = SessionLocal()
        try:
            entry = QueueEngineService.join_queue(
                db=worker_db,
                queue_id=queue_id,
                patient_user_id=patient_id,
                priority_class=PriorityClass.NORMAL,
            )
            return entry.token_number
        finally:
            worker_db.close()

    def worker_staff(idx):
        worker_db = SessionLocal()
        try:
            entry = QueueEngineService.staff_book_appointment(
                db=worker_db,
                queue_id=queue_id,
                staff_user_id=staff_id,
                patient_name=f"Walkin Concur {idx}",
                booking_source="WALK_IN",
                priority_class=PriorityClass.NORMAL,
            )
            return entry.token_number
        finally:
            worker_db.close()

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        # 4 patient online joins
        for pid in patient_ids:
            futures.append(executor.submit(worker_patient, pid))
        # 4 staff walk-in bookings
        for idx in range(4):
            futures.append(executor.submit(worker_staff, idx))

        for f in as_completed(futures):
            results.append(f.result())

    assert len(results) == 8
    assert len(set(results)) == 8, f"Duplicate tokens found in concurrent test: {results}"
    assert sorted(results) == list(range(1, 9)), f"Expected tokens 1..8, got {sorted(results)}"


# 4. Different doctors / queues isolation
def test_different_doctors_queues_isolation(test_client: TestClient, db_session):
    hospital = Hospital(name="Multi Doctor Hospital", address="Health Way")
    db_session.add(hospital)
    db_session.commit()
    db_session.refresh(hospital)

    dept = Department(hospital_id=hospital.id, name="Cardio & Ortho")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    # Doctor 1 & Queue 1
    doc1 = Doctor(department_id=dept.id, name="Dr. Cardio", status=DoctorStatus.AVAILABLE)
    db_session.add(doc1)
    db_session.commit()
    db_session.refresh(doc1)

    sess1 = OPDSession(department_id=dept.id, doctor_id=doc1.id, starts_at=datetime.now(timezone.utc), status=SessionStatus.ACTIVE)
    db_session.add(sess1)
    db_session.commit()
    db_session.refresh(sess1)

    q1 = Queue(opd_session_id=sess1.id, name="Cardio Queue", status=QueueStatus.ACTIVE)
    db_session.add(q1)
    db_session.commit()
    db_session.refresh(q1)

    from datetime import date, time as dt_time
    from app.models.doctor_schedule import DoctorSchedule
    sched1 = DoctorSchedule(
        hospital_id=hospital.id,
        department_id=dept.id,
        doctor_id=doc1.id,
        schedule_date=date.today(),
        start_time=dt_time(8, 0),
        end_time=dt_time(18, 0),
        status="AVAILABLE",
        opd_session_id=sess1.id,
    )
    db_session.add(sched1)

    # Doctor 2 & Queue 2
    doc2 = Doctor(department_id=dept.id, name="Dr. Ortho", status=DoctorStatus.AVAILABLE)
    db_session.add(doc2)
    db_session.commit()
    db_session.refresh(doc2)

    sess2 = OPDSession(department_id=dept.id, doctor_id=doc2.id, starts_at=datetime.now(timezone.utc), status=SessionStatus.ACTIVE)
    db_session.add(sess2)
    db_session.commit()
    db_session.refresh(sess2)

    q2 = Queue(opd_session_id=sess2.id, name="Ortho Queue", status=QueueStatus.ACTIVE)
    db_session.add(q2)

    sched2 = DoctorSchedule(
        hospital_id=hospital.id,
        department_id=dept.id,
        doctor_id=doc2.id,
        schedule_date=date.today(),
        start_time=dt_time(8, 0),
        end_time=dt_time(18, 0),
        status="AVAILABLE",
        opd_session_id=sess2.id,
    )
    db_session.add(sched2)
    db_session.commit()
    db_session.refresh(q2)

    p1, h1 = create_user_with_token(db_session, "Pat 1", f"p1_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
    p2, h2 = create_user_with_token(db_session, "Pat 2", f"p2_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)

    # Join Q1
    r1 = test_client.post(f"/api/v1/queues/{q1.id}/join", json={"priority": "NORMAL"}, headers=h1)
    assert r1.status_code == 201
    assert r1.json()["entry"]["token_number"] == 1

    # Join Q2
    r2 = test_client.post(f"/api/v1/queues/{q2.id}/join", json={"priority": "NORMAL"}, headers=h2)
    assert r2.status_code == 201
    assert r2.json()["entry"]["token_number"] == 1  # Independent sequence starts at 1!


# 5. Different hospitals isolation
def test_different_hospitals_isolation(test_client: TestClient, db_session):
    h1, _, _, _, q1 = create_test_hospital_hierarchy(db_session, "Hospital Alpha")
    h2, _, _, _, q2 = create_test_hospital_hierarchy(db_session, "Hospital Beta")

    p1, auth1 = create_user_with_token(db_session, "User Alpha", f"u1_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
    p2, auth2 = create_user_with_token(db_session, "User Beta", f"u2_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)

    # Hospital Alpha booking
    resp1 = test_client.post(f"/api/v1/queues/{q1.id}/join", json={"priority": "NORMAL"}, headers=auth1)
    assert resp1.status_code == 201
    assert resp1.json()["entry"]["token_number"] == 1

    # Hospital Beta booking
    resp2 = test_client.post(f"/api/v1/queues/{q2.id}/join", json={"priority": "NORMAL"}, headers=auth2)
    assert resp2.status_code == 201
    assert resp2.json()["entry"]["token_number"] == 1


# 6. Cross-hospital staff access denial (HTTP 403)
def test_cross_hospital_staff_access_denial(test_client: TestClient, db_session):
    h1, _, _, _, q1 = create_test_hospital_hierarchy(db_session, "Hospital One")
    h2, _, _, _, q2 = create_test_hospital_hierarchy(db_session, "Hospital Two")

    # Staff 1 belongs to Hospital One ONLY
    staff1, staff1_headers = create_user_with_token(
        db_session, "Staff One", f"s1_{uuid.uuid4().hex[:6]}@test.com", UserRole.STAFF, hospital_id=h1.id
    )

    # Staff 1 tries to staff-book into Hospital Two's queue -> Must fail 403 Forbidden!
    denied_resp = test_client.post(
        f"/api/v1/queues/{q2.id}/staff-book",
        json={
            "patient_name": "Intruder Patient",
            "booking_source": "WALK_IN",
            "priority": "NORMAL",
        },
        headers=staff1_headers,
    )
    assert denied_resp.status_code == 403
    assert "Access denied" in denied_resp.json()["detail"] or "Forbidden" in denied_resp.json()["detail"]

    # Staff 1 tries to call next in Hospital Two's queue -> Must fail 403 Forbidden!
    denied_call = test_client.post(
        f"/api/v1/queues/{q2.id}/call-next",
        headers=staff1_headers,
    )
    assert denied_call.status_code == 403
    assert "Access denied" in denied_call.json()["detail"] or "Forbidden" in denied_call.json()["detail"]

    # Staff 1 operates in Hospital One's queue -> Succeeds
    allowed_resp = test_client.post(
        f"/api/v1/queues/{q1.id}/staff-book",
        json={
            "patient_name": "Valid Walkin",
            "booking_source": "WALK_IN",
            "priority": "NORMAL",
        },
        headers=staff1_headers,
    )
    assert allowed_resp.status_code == 201


# 7. Patient access to only their own appointments
def test_patient_access_only_own_appointments(test_client: TestClient, db_session):
    hospital, _, _, _, queue = create_test_hospital_hierarchy(db_session, "Patient Isolation Hospital")

    p1, h1 = create_user_with_token(db_session, "Patient 1", f"p1_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
    p2, h2 = create_user_with_token(db_session, "Patient 2", f"p2_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)

    # Patient 1 books
    resp1 = test_client.post(f"/api/v1/queues/{queue.id}/join", json={"priority": "NORMAL"}, headers=h1)
    entry1_id = resp1.json()["entry"]["id"]

    # Patient 2 books
    resp2 = test_client.post(f"/api/v1/queues/{queue.id}/join", json={"priority": "NORMAL"}, headers=h2)
    entry2_id = resp2.json()["entry"]["id"]

    # Patient 1 checks /my appointments
    my1_resp = test_client.get("/api/v1/queue-entries/my", headers=h1)
    assert my1_resp.status_code == 200
    my1_data = my1_resp.json()
    my1_ids = [item["id"] for item in my1_data["today"] + my1_data["upcoming"] + my1_data["past"]]
    assert entry1_id in my1_ids
    assert entry2_id not in my1_ids

    # Patient 2 checks /my appointments
    my2_resp = test_client.get("/api/v1/queue-entries/my", headers=h2)
    assert my2_resp.status_code == 200
    my2_data = my2_resp.json()
    my2_ids = [item["id"] for item in my2_data["today"] + my2_data["upcoming"] + my2_data["past"]]
    assert entry2_id in my2_ids
    assert entry1_id not in my2_ids

    # Patient 1 tries to access Patient 2's specific entry -> 403 Forbidden!
    cross_resp = test_client.get(f"/api/v1/queue-entries/{entry2_id}", headers=h1)
    assert cross_resp.status_code == 403


# 8. Google Maps / API failure handling
def test_google_maps_failure_handling(test_client: TestClient, db_session):
    hospital, _, _, _, queue = create_test_hospital_hierarchy(db_session, "Travel Hospital")
    p, h = create_user_with_token(db_session, "Travel Patient", f"tp_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)

    # Patient joins queue
    resp = test_client.post(f"/api/v1/queues/{queue.id}/join", json={"priority": "NORMAL"}, headers=h)
    assert resp.status_code == 201
    entry_id = resp.json()["entry"]["id"]

    # 1. Travel estimate when origin is not yet set -> UNAVAILABLE status without crashing
    travel_resp1 = test_client.get(f"/api/v1/queue-entries/{entry_id}/travel", headers=h)
    assert travel_resp1.status_code == 200
    data1 = travel_resp1.json()
    assert data1["travel_status"] == "UNAVAILABLE"
    assert data1["travel_duration_seconds"] is None

    # 2. Set origin coordinates and check travel estimate
    set_origin_resp = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/travel-origin",
        json={"latitude": 12.9716, "longitude": 77.5946, "travel_mode": "DRIVE"},
        headers=h,
    )
    assert set_origin_resp.status_code == 200

    # 3. Query travel estimate: must return 200 with honest status without crashing
    travel_resp2 = test_client.get(f"/api/v1/queue-entries/{entry_id}/travel", headers=h)
    assert travel_resp2.status_code == 200
    data2 = travel_resp2.json()
    assert data2["travel_status"] in ["OPTIMIZED", "OK", "DEGRADED", "UNAVAILABLE", "CONFIGURATION_REQUIRED"]
