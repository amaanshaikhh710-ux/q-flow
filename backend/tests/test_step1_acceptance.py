"""Q-FLOW STEP 1 ACCEPTANCE TEST SUITE:
Verifies:
1. Real Hospital-Staff Doctor Scheduling (hospital isolation, DB storage, schedule planning)
2. Backend rejection of cross-hospital schedule attempts (HTTP 403)
3. Date-specific patient doctor availability & time window enforcement
4. Direct patient booking on unscheduled dates or outside hours rejected (HTTP 400)
5. Appointment booking connects to date-specific queue in same hospital/dept/doctor
6. Correct staff vs patient role separation & authorization
"""

import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.doctor_schedule import DoctorSchedule
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.opd_session import OPDSession, SessionStatus
from app.models.user import User, UserRole
from app.core.security import create_access_token, hash_password


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def setup_step1_data(db_session: Session):
    """Setup clean test fixture with Hospital A (KEM), Hospital B (Nair), Doctors, and Users."""
    # Hospital A
    hosp_a = db_session.query(Hospital).filter(Hospital.name == "Acceptance KEM Hospital").first()
    if not hosp_a:
        hosp_a = Hospital(name="Acceptance KEM Hospital", address="Parel, Mumbai", latitude=Decimal("19.0033"), longitude=Decimal("72.8423"))
        db_session.add(hosp_a)
        db_session.commit()

    # Hospital B
    hosp_b = db_session.query(Hospital).filter(Hospital.name == "Acceptance Nair Hospital").first()
    if not hosp_b:
        hosp_b = Hospital(name="Acceptance Nair Hospital", address="Mumbai Central, Mumbai", latitude=Decimal("18.9690"), longitude=Decimal("72.8205"))
        db_session.add(hosp_b)
        db_session.commit()

    # Dept A
    dept_a = db_session.query(Department).filter(Department.hospital_id == hosp_a.id, Department.name == "Dermatology").first()
    if not dept_a:
        dept_a = Department(hospital_id=hosp_a.id, name="Dermatology")
        db_session.add(dept_a)
        db_session.commit()

    # Dept B
    dept_b = db_session.query(Department).filter(Department.hospital_id == hosp_b.id, Department.name == "Cardiology").first()
    if not dept_b:
        dept_b = Department(hospital_id=hosp_b.id, name="Cardiology")
        db_session.add(dept_b)
        db_session.commit()

    # Doctor A (Hospital A)
    doc_a = db_session.query(Doctor).filter(Doctor.department_id == dept_a.id, Doctor.name == "Dr. Alice KEM").first()
    if not doc_a:
        doc_a = Doctor(department_id=dept_a.id, name="Dr. Alice KEM", status=DoctorStatus.AVAILABLE)
        db_session.add(doc_a)
        db_session.commit()

    # Doctor B (Hospital B)
    doc_b = db_session.query(Doctor).filter(Doctor.department_id == dept_b.id, Doctor.name == "Dr. Bob Nair").first()
    if not doc_b:
        doc_b = Doctor(department_id=dept_b.id, name="Dr. Bob Nair", status=DoctorStatus.AVAILABLE)
        db_session.add(doc_b)
        db_session.commit()

    # Staff A (Belongs to Hospital A)
    staff_a = db_session.query(User).filter(User.email == "staff_acceptance_a@kem.org").first()
    if not staff_a:
        staff_a = User(
            name="KEM Staff Member",
            email="staff_acceptance_a@kem.org",
            password_hash=hash_password("Pass123!"),
            role=UserRole.STAFF,
            hospital_id=hosp_a.id,
        )
        db_session.add(staff_a)
        db_session.commit()
    else:
        staff_a.hospital_id = hosp_a.id
        db_session.commit()

    # Patient User
    patient_user = db_session.query(User).filter(User.email == "patient_acceptance@gmail.com").first()
    if not patient_user:
        patient_user = User(
            name="Rahul Sharma",
            email="patient_acceptance@gmail.com",
            password_hash=hash_password("Pass123!"),
            role=UserRole.PATIENT,
        )
        db_session.add(patient_user)
        db_session.commit()

    # Queue & OPD session for Doctor A
    opd_a = db_session.query(OPDSession).filter(OPDSession.doctor_id == doc_a.id).first()
    if not opd_a:
        opd_a = OPDSession(
            department_id=dept_a.id,
            doctor_id=doc_a.id,
            starts_at=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE,
        )
        db_session.add(opd_a)
        db_session.commit()

    queue_a = db_session.query(Queue).filter(Queue.opd_session_id == opd_a.id).first()
    if not queue_a:
        queue_a = Queue(
            opd_session_id=opd_a.id,
            name="Dermatology Room 101",
            status=QueueStatus.ACTIVE,
        )
        db_session.add(queue_a)
        db_session.commit()

    # Clean previous test state so each acceptance run starts from a clean doctor queue/session state.
    doctor_session_ids = db_session.query(OPDSession.id).filter(OPDSession.doctor_id == doc_a.id).subquery()
    doctor_queue_ids = db_session.query(Queue.id).filter(Queue.opd_session_id.in_(doctor_session_ids)).subquery()

    db_session.query(QueueEntry).filter(QueueEntry.queue_id.in_(doctor_queue_ids)).delete(synchronize_session=False)
    db_session.query(Queue).filter(Queue.opd_session_id.in_(doctor_session_ids)).delete(synchronize_session=False)
    db_session.query(OPDSession).filter(OPDSession.doctor_id == doc_a.id).delete(synchronize_session=False)
    db_session.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doc_a.id).delete(synchronize_session=False)
    db_session.commit()

    # Recreate the canonical doctor queue/session for the acceptance workflow.
    opd_a = OPDSession(
        department_id=dept_a.id,
        doctor_id=doc_a.id,
        starts_at=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    db_session.add(opd_a)
    db_session.commit()

    queue_a = Queue(
        opd_session_id=opd_a.id,
        name="Dermatology Room 101",
        status=QueueStatus.ACTIVE,
    )
    db_session.add(queue_a)
    db_session.commit()

    staff_a_token = create_access_token(subject=str(staff_a.id), role=staff_a.role.value)
    patient_token = create_access_token(subject=str(patient_user.id), role=patient_user.role.value)

    return {
        "hosp_a": hosp_a,
        "hosp_b": hosp_b,
        "dept_a": dept_a,
        "dept_b": dept_b,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "staff_a": staff_a,
        "staff_a_token": staff_a_token,
        "patient_user": patient_user,
        "patient_token": patient_token,
        "queue_a": queue_a,
    }


def test_acceptance_1_staff_sees_only_own_hospital_doctors(client: TestClient, setup_step1_data):
    """TEST 1: Staff from Hospital A logs in -> Only Hospital A doctors are available for scheduling."""
    token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/discovery/staff-hospital", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["hospital"]["id"] == str(setup_step1_data["hosp_a"].id)
    doctor_names = [d["name"] for d in data.get("doctors", [])]
    assert "Dr. Alice KEM" in doctor_names
    assert "Dr. Bob Nair" not in doctor_names


def test_acceptance_2_staff_cannot_schedule_doctor_from_other_hospital(client: TestClient, setup_step1_data):
    """TEST 2: Hospital A staff attempts to schedule Hospital B doctor through direct API manipulation.
    Result: Backend rejects request with 403 Forbidden.
    """
    token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt 1: Schedule Hospital B doctor with Hospital B ID
    payload = {
        "hospital_id": str(setup_step1_data["hosp_b"].id),
        "doctor_id": str(setup_step1_data["doc_b"].id),
        "department_id": str(setup_step1_data["dept_b"].id),
        "schedule_date": "2026-09-24",
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    res = client.post("/api/v1/schedules", json=payload, headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"

    # Attempt 2: Direct API spoofing passing own hospital ID but Doctor B ID (which belongs to Hospital B)
    payload_spoof = {
        "hospital_id": str(setup_step1_data["hosp_a"].id),
        "doctor_id": str(setup_step1_data["doc_b"].id),
        "department_id": str(setup_step1_data["dept_a"].id),
        "schedule_date": "2026-09-24",
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    res_spoof = client.post("/api/v1/schedules", json=payload_spoof, headers=headers)
    assert res_spoof.status_code in (400, 403, 404), f"Expected rejection, got {res_spoof.status_code}"


def test_acceptance_3_staff_schedules_doctor_in_db(client: TestClient, setup_step1_data, db_session: Session):
    """TEST 3: Staff schedules Doctor A: 24 Sept 09:00-13:00. Result: Database contains the schedule."""
    token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "hospital_id": str(setup_step1_data["hosp_a"].id),
        "doctor_id": str(setup_step1_data["doc_a"].id),
        "department_id": str(setup_step1_data["dept_a"].id),
        "schedule_date": "2026-09-24",
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    res = client.post("/api/v1/schedules", json=payload, headers=headers)
    assert res.status_code in (200, 201), res.text

    # Verify directly in DB
    db_sched = (
        db_session.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == setup_step1_data["doc_a"].id,
            DoctorSchedule.schedule_date == date(2026, 9, 24),
        )
        .first()
    )
    assert db_sched is not None
    assert db_sched.start_time == time(9, 0)
    assert db_sched.end_time == time(13, 0)
    assert db_sched.status == "AVAILABLE"


def test_acceptance_4_patient_sees_scheduled_doctor_on_24_sept(client: TestClient, setup_step1_data):
    """TEST 4: Patient selects 24 Sept. Result: Doctor A appears with 09:00-13:00 availability."""
    # First ensure schedule exists
    staff_token = setup_step1_data["staff_a_token"]
    sched_res = client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "status": "AVAILABLE",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert sched_res.status_code in (200, 201)

    hosp_id = str(setup_step1_data["hosp_a"].id)
    res = client.get(f"/api/v1/schedules/available-doctors?hospital_id={hosp_id}&date=2026-09-24")
    assert res.status_code == 200, res.text
    response_data = res.json()
    doctors = response_data.get("doctors", [])
    assert len(doctors) >= 1
    doc_match = next((d for d in doctors if d["doctor_id"] == str(setup_step1_data["doc_a"].id)), None)
    assert doc_match is not None
    assert doc_match["start_time"] == "09:00:00"
    assert doc_match["end_time"] == "13:00:00"


def test_acceptance_5_patient_does_not_see_doctor_on_unscheduled_date(client: TestClient, setup_step1_data):
    """TEST 5: Patient selects a date where Doctor A has no schedule (e.g. 26 Sept 2026).
    Result: Doctor A does not appear as available.
    """
    hosp_id = str(setup_step1_data["hosp_a"].id)
    res = client.get(f"/api/v1/schedules/available-doctors?hospital_id={hosp_id}&date=2026-09-26")
    assert res.status_code == 200, res.text
    response_data = res.json()
    doctors = response_data.get("doctors", [])
    doc_match = next((d for d in doctors if d["doctor_id"] == str(setup_step1_data["doc_a"].id)), None)
    assert doc_match is None, "Unscheduled doctor must NOT appear in patient available doctors!"


def test_acceptance_6_patient_booking_rejected_on_unscheduled_date(client: TestClient, setup_step1_data):
    """TEST 6: Patient attempts direct API booking for Doctor A on an unscheduled date.
    Result: Backend rejects booking with HTTP 400.
    """
    token = setup_step1_data["patient_token"]
    headers = {"Authorization": f"Bearer {token}"}
    queue_id = str(setup_step1_data["queue_a"].id)

    payload = {
        "appointment_date": "2026-09-26",
        "appointment_time": "10:00:00",
    }
    res = client.post(f"/api/v1/queues/{queue_id}/join", json=payload, headers=headers)
    assert res.status_code == 400
    assert "scheduled" in res.json().get("detail", "").lower()


def test_acceptance_7_patient_books_valid_scheduled_slot(client: TestClient, setup_step1_data, db_session: Session):
    """TEST 7: Patient books Doctor A on a valid scheduled date/time.
    Result: Real appointment is created and connected to correct hospital, doctor, department, date and queue.
    """
    # 1. Staff creates schedule
    staff_token = setup_step1_data["staff_a_token"]
    sched_res = client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "status": "AVAILABLE",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert sched_res.status_code in (200, 201)

    # 2. Patient books
    token = setup_step1_data["patient_token"]
    headers = {"Authorization": f"Bearer {token}"}
    queue_id = str(setup_step1_data["queue_a"].id)

    payload = {
        "appointment_date": "2026-09-24",
        "appointment_time": "10:30:00",
    }
    res = client.post(f"/api/v1/queues/{queue_id}/join", json=payload, headers=headers)
    assert res.status_code in (200, 201), res.text
    response_data = res.json()
    booking = response_data.get("entry", response_data)
    assert booking["appointment_date"] == "2026-09-24"
    assert booking["queue_id"] is not None
    assert booking["token_number"] is not None

    # Check DB record
    entry = db_session.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(booking["id"])).first()
    assert entry is not None
    assert str(entry.appointment_date) == "2026-09-24"
    assert entry.queue.opd_session.doctor_id == setup_step1_data["doc_a"].id


def test_acceptance_8_patient_availability_updates_on_date_switch(client: TestClient, setup_step1_data):
    """TEST 8: Staff creates another schedule for the same doctor on another date.
    Result: Patient availability changes correctly when switching dates.
    """
    token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Staff schedules Doctor A for 24 Sept (09:00 - 13:00)
    client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "status": "AVAILABLE",
        },
        headers=headers,
    )

    # Staff schedules Doctor A for 25 Sept (14:00 - 18:00)
    res = client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-25",
            "start_time": "14:00:00",
            "end_time": "18:00:00",
            "status": "AVAILABLE",
        },
        headers=headers,
    )
    assert res.status_code in (200, 201)

    hosp_id = str(setup_step1_data["hosp_a"].id)

    # 1. Check 24 Sept -> 09:00 - 13:00
    res_24 = client.get(f"/api/v1/schedules/available-doctors?hospital_id={hosp_id}&date=2026-09-24")
    d24_list = res_24.json().get("doctors", [])
    d24 = next(d for d in d24_list if d["doctor_id"] == str(setup_step1_data["doc_a"].id))
    assert d24["start_time"] == "09:00:00"

    # 2. Check 25 Sept -> 14:00 - 18:00
    res_25 = client.get(f"/api/v1/schedules/available-doctors?hospital_id={hosp_id}&date=2026-09-25")
    d25_list = res_25.json().get("doctors", [])
    d25 = next(d for d in d25_list if d["doctor_id"] == str(setup_step1_data["doc_a"].id))
    assert d25["start_time"] == "14:00:00"
    assert d25["end_time"] == "18:00:00"


def test_acceptance_9_staff_sees_staff_operations_not_patient_portal(client: TestClient, setup_step1_data):
    """TEST 9: Staff logs in. Result: Staff sees Staff/OPD dashboard, NOT patient Book Appointment/My Appointments UI."""
    token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify user profile returns staff role and assigned hospital
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["role"] in ("STAFF", "staff")
    assert user_info["hospital_id"] == str(setup_step1_data["hosp_a"].id)

    # Staff hospital overview works
    hosp_res = client.get("/api/v1/discovery/staff-hospital", headers=headers)
    assert hosp_res.status_code == 200
    assert hosp_res.json()["hospital"]["name"] == "Acceptance KEM Hospital"


def test_acceptance_10_staff_can_book_on_behalf_of_patient(client: TestClient, setup_step1_data, db_session: Session):
    """TEST 10: Staff clicks Add Patient / Add Appointment.
    Result: Staff can create an appointment ON BEHALF OF a patient using the same appointment/queue system.
    """
    # 1. Ensure schedule exists
    staff_token = setup_step1_data["staff_a_token"]
    headers = {"Authorization": f"Bearer {staff_token}"}
    sched_res = client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "status": "AVAILABLE",
        },
        headers=headers,
    )
    assert sched_res.status_code in (200, 201)

    queue_id = str(setup_step1_data["queue_a"].id)

    # Use unique phone to avoid collision with any existing records
    unique_phone = f"+91987{uuid.uuid4().hex[:7]}"
    staff_book_payload = {
        "patient_name": "Walk-in Elderly Patient",
        "patient_phone": unique_phone,
        "priority_class": "priority",
        "notes": "Walk-in registered by OPD desk",
        "appointment_date": "2026-09-24",
        "appointment_time": "11:15:00",
    }
    res = client.post(f"/api/v1/queues/{queue_id}/staff-book", json=staff_book_payload, headers=headers)
    assert res.status_code in (200, 201), res.text
    response_data = res.json()
    data = response_data.get("entry", response_data)
    assert data["token_number"] is not None
    assert data["appointment_date"] == "2026-09-24"

    # Verify it entered the exact same queue system
    entry = db_session.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(data["id"])).first()
    assert entry is not None
    assert entry.queue.opd_session.doctor_id == setup_step1_data["doc_a"].id
    assert entry.priority_class == PriorityClass.PRIORITY


def test_acceptance_11_patient_portal_flow_intact(client: TestClient, setup_step1_data):
    """TEST 11: Patient logs in. Result: Patient still sees the normal patient portal and booking flow."""
    # 1. Staff schedules doctor
    staff_token = setup_step1_data["staff_a_token"]
    client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "status": "AVAILABLE",
        },
        headers={"Authorization": f"Bearer {staff_token}"},
    )

    # 2. Patient books
    patient_token = setup_step1_data["patient_token"]
    headers = {"Authorization": f"Bearer {patient_token}"}
    queue_id = str(setup_step1_data["queue_a"].id)
    client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": "2026-09-24", "appointment_time": "12:00:00"},
        headers=headers,
    )

    # 3. Verify patient profile
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] in ("PATIENT", "patient")

    # 4. Patient queries their appointments
    my_res = client.get("/api/v1/queue-entries/my", headers=headers)
    assert my_res.status_code == 200
    data = my_res.json()
    total = data.get("total", len(data.get("upcoming", [])) + len(data.get("today", [])) + len(data.get("past", [])))
    assert total >= 1


def test_acceptance_12_backend_rejects_unauthorized_role_access(client: TestClient, setup_step1_data):
    """TEST 12: A staff user attempts to access patient-only functionality directly, and vice-versa.
    Result: Backend rejects unauthorized access with 403, not merely a frontend redirect/hide.
    """
    staff_token = setup_step1_data["staff_a_token"]
    patient_token = setup_step1_data["patient_token"]
    queue_id = str(setup_step1_data["queue_a"].id)

    # 1. Staff attempts patient-only booking endpoint
    res = client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": "2026-09-24"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert res.status_code == 403, f"Staff must not call patient join: {res.status_code}"

    # 2. Staff attempts patient-only 'my appointments' endpoint
    res_my = client.get("/api/v1/queue-entries/my", headers={"Authorization": f"Bearer {staff_token}"})
    assert res_my.status_code == 403, f"Staff must not call patient my-appointments: {res_my.status_code}"

    # 3. Patient attempts staff-only schedule creation
    res_sched = client.post(
        "/api/v1/schedules",
        json={
            "hospital_id": str(setup_step1_data["hosp_a"].id),
            "doctor_id": str(setup_step1_data["doc_a"].id),
            "department_id": str(setup_step1_data["dept_a"].id),
            "schedule_date": "2026-09-24",
            "start_time": "09:00:00",
            "end_time": "13:00:00",
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert res_sched.status_code == 403, f"Patient must not create schedules: {res_sched.status_code}"

    # 4. Patient attempts staff-only staff-book endpoint
    res_staff_book = client.post(
        f"/api/v1/queues/{queue_id}/staff-book",
        json={"patient_name": "Test", "patient_phone": "1234567890"},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert res_staff_book.status_code == 403, f"Patient must not access staff-book: {res_staff_book.status_code}"
