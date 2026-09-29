"""Mandatory 17-Step End-to-End Acceptance Test for Doctor OPD Scheduling,
Date-Specific Queues, Patient Availability, and Phone/Walk-in Booking.
"""

import uuid
from datetime import date, timedelta
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
from app.models.opd_session import OPDSession
from app.models.user import User, UserRole


@pytest.fixture
def db_session():
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_mandatory_17_step_opd_scheduling_e2e(client: TestClient, db_session: Session):
    """
    Executes the exact 17-step end-to-end acceptance test mandated by the requirements:
    1. Login as KEM staff.
    2. Open Staff Portal.
    3. Find 'Doctor OPD Schedule'.
    4. Click '+ Schedule Doctor OPD'.
    5. Select an EXISTING KEM doctor (Dr. Arjun Mehta).
    6. Schedule: Tomorrow 09:00 AM – 01:00 PM.
    7. Save.
    8. Refresh browser (verify DB persistence).
    9. Login as patient.
    10. Select KEM.
    11. Select the same doctor -> Tomorrow appears as an available date.
    12. Select tomorrow -> 09:00 AM – 01:00 PM appears.
    13. Book an appointment -> Appointment is created.
    14. Login/open staff queue.
    15. Select tomorrow -> Patient appears in the same doctor's queue for tomorrow.
    16. Add another patient through phone/walk-in -> Added to the SAME queue.
    17. Verify token numbers -> No duplicate tokens, strictly sequential.
    + Hospital isolation and unscheduled booking rejection verified.
    """

    from app.core.security import hash_password

    # Setup / Ensure KEM Hospital
    hosp_kem = db_session.query(Hospital).filter(Hospital.name.like("%KEM%")).first()
    if not hosp_kem:
        hosp_kem = Hospital(
            name="King Edward Memorial (KEM) Hospital",
            address="Acharya Donde Marg, Parel, Mumbai",
            latitude=Decimal("19.0026"),
            longitude=Decimal("72.8423"),
        )
        db_session.add(hosp_kem)
        db_session.flush()

    # Setup / Ensure Nair Hospital
    hosp_nair = db_session.query(Hospital).filter(Hospital.name.like("%Nair%")).first()
    if not hosp_nair:
        hosp_nair = Hospital(
            name="BYL Nair Charitable Hospital",
            address="Mumbai Central, Mumbai",
            latitude=Decimal("18.9712"),
            longitude=Decimal("72.8228"),
        )
        db_session.add(hosp_nair)
        db_session.flush()

    # Setup / Ensure KEM Department
    dept_kem = db_session.query(Department).filter(Department.hospital_id == hosp_kem.id).first()
    if not dept_kem:
        dept_kem = Department(hospital_id=hosp_kem.id, name="General Medicine")
        db_session.add(dept_kem)
        db_session.flush()

    # Setup / Ensure Dr. Arjun Mehta at KEM
    doc_arjun = db_session.query(Doctor).filter(Doctor.name.like("%Arjun%")).first()
    if not doc_arjun:
        doc_arjun = Doctor(
            department_id=dept_kem.id,
            name="Dr. Arjun Mehta",
            status=DoctorStatus.AVAILABLE,
        )
        db_session.add(doc_arjun)
        db_session.flush()

    # Setup / Ensure KEM Staff user
    kem_staff = db_session.query(User).filter(User.email == "staff.kem@qflow.com").first()
    if not kem_staff:
        kem_staff = User(
            name="Sunil More",
            email="staff.kem@qflow.com",
            password_hash=hash_password("password123"),
            role=UserRole.STAFF,
            hospital_id=hosp_kem.id,
        )
        db_session.add(kem_staff)
        db_session.flush()
    else:
        kem_staff.password_hash = hash_password("password123")
        kem_staff.hospital_id = hosp_kem.id
        db_session.flush()

    # Setup / Ensure Nair Staff user
    nair_staff = db_session.query(User).filter(User.email == "staff.nair@qflow.com").first()
    if not nair_staff:
        nair_staff = User(
            name="Pooja Varma",
            email="staff.nair@qflow.com",
            password_hash=hash_password("password123"),
            role=UserRole.STAFF,
            hospital_id=hosp_nair.id,
        )
        db_session.add(nair_staff)
        db_session.flush()
    else:
        nair_staff.password_hash = hash_password("password123")
        nair_staff.hospital_id = hosp_nair.id
        db_session.flush()

    # Setup / Ensure Patient user
    patient_user = db_session.query(User).filter(User.email == "patient@qflow.com").first()
    if not patient_user:
        patient_user = User(
            name="Aisha Khan",
            email="patient@qflow.com",
            password_hash=hash_password("password123"),
            role=UserRole.PATIENT,
        )
        db_session.add(patient_user)
        db_session.flush()
    else:
        patient_user.password_hash = hash_password("password123")
        db_session.flush()

    db_session.commit()

    tomorrow = date.today() + timedelta(days=1)
    unscheduled_date = date.today() + timedelta(days=5)

    # -------------------------------------------------------------------------
    # STEP 1: Login as KEM staff
    # -------------------------------------------------------------------------
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "staff.kem@qflow.com", "password": "password123"},
    )
    assert login_resp.status_code == 200, f"Staff login failed: {login_resp.text}"
    staff_auth = login_resp.json()
    staff_token = staff_auth["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Fetch current user profile to verify KEM hospital binding
    me_resp = client.get("/api/v1/auth/me", headers=staff_headers)
    assert me_resp.status_code == 200
    staff_profile = me_resp.json()
    assert staff_profile["role"] == "staff"
    kem_hospital_id = staff_profile["hospital_id"]
    assert kem_hospital_id is not None, "KEM staff must have a valid hospital_id"

    # -------------------------------------------------------------------------
    # STEP 2, 3, 4: Open Staff Portal & Find Doctor OPD Schedule
    # Verify staff can access existing hospital departments and doctors
    # -------------------------------------------------------------------------
    staff_hosp_resp = client.get("/api/v1/discovery/staff-hospital", headers=staff_headers)
    assert staff_hosp_resp.status_code == 200
    staff_hosp_data = staff_hosp_resp.json()
    assert "KEM" in staff_hosp_data["hospital"]["name"]

    dept_resp = client.get(f"/api/v1/discovery/hospitals/{kem_hospital_id}/departments")
    assert dept_resp.status_code == 200
    departments = dept_resp.json()
    assert len(departments) > 0, "KEM must have departments"
    dept_kem_item = next((d for d in departments if "Medicine" in d["name"]), departments[0])
    kem_dept_id = dept_kem_item["id"]

    # -------------------------------------------------------------------------
    # STEP 5: Select an EXISTING KEM doctor (Dr. Arjun Mehta)
    # -------------------------------------------------------------------------
    doc_resp = client.get(f"/api/v1/discovery/departments/{kem_dept_id}/doctors")
    assert doc_resp.status_code == 200
    doctors = doc_resp.json()
    arjun_doc = next((d for d in doctors if "Arjun" in d["name"]), None)
    assert arjun_doc is not None, "Dr. Arjun Mehta must exist at KEM"
    doctor_id = arjun_doc["id"]
    department_id = arjun_doc["department_id"]

    # Clean any pre-existing test schedule for tomorrow to ensure test purity
    db_session.query(QueueEntry).filter(
        QueueEntry.appointment_date == tomorrow
    ).delete(synchronize_session=False)
    db_session.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == uuid.UUID(doctor_id),
        DoctorSchedule.schedule_date == tomorrow,
    ).delete(synchronize_session=False)
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 6 & 7: Schedule: Tomorrow 09:00 AM – 01:00 PM and Save
    # -------------------------------------------------------------------------
    create_schedule_payload = {
        "doctor_id": doctor_id,
        "department_id": department_id,
        "schedule_date": str(tomorrow),
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    save_resp = client.post(
        "/api/v1/schedules",
        json=create_schedule_payload,
        headers=staff_headers,
    )
    assert save_resp.status_code == 201, f"Save schedule failed: {save_resp.text}"
    schedule_data = save_resp.json()
    assert schedule_data["doctor_name"] == arjun_doc["name"]
    assert schedule_data["schedule_date"] == str(tomorrow)
    assert schedule_data["start_time_formatted"] == "09:00 AM"
    assert schedule_data["end_time_formatted"] == "01:00 PM"
    assert schedule_data["queue_id"] is not None
    queue_id = schedule_data["queue_id"]

    # -------------------------------------------------------------------------
    # STEP 8: Refresh browser (verify DB persistence)
    # -------------------------------------------------------------------------
    # Query schedules endpoint again
    query_resp = client.get(
        f"/api/v1/schedules?doctor_id={doctor_id}&start_date={tomorrow}&end_date={tomorrow}",
        headers=staff_headers,
    )
    assert query_resp.status_code == 200
    persisted_schedules = query_resp.json()
    assert len(persisted_schedules) == 1
    assert persisted_schedules[0]["schedule_date"] == str(tomorrow)
    assert persisted_schedules[0]["start_time_formatted"] == "09:00 AM"
    assert persisted_schedules[0]["end_time_formatted"] == "01:00 PM"

    # Also verify direct database row exists
    db_record = db_session.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == uuid.UUID(doctor_id),
        DoctorSchedule.schedule_date == tomorrow,
    ).first()
    assert db_record is not None, "Database record must physically exist in doctor_schedules table"
    assert db_record.start_time.strftime("%H:%M") == "09:00"
    assert db_record.end_time.strftime("%H:%M") == "13:00"

    # -------------------------------------------------------------------------
    # STEP 9: Login as patient
    # -------------------------------------------------------------------------
    patient_login_resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "patient@qflow.com", "password": "password123"},
    )
    assert patient_login_resp.status_code == 200, f"Patient login failed: {patient_login_resp.text}"
    patient_auth = patient_login_resp.json()
    patient_token = patient_auth["access_token"]
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    # -------------------------------------------------------------------------
    # STEP 10 & 11: Select KEM -> Select Dr. Arjun Mehta -> Tomorrow is AVAILABLE
    # -------------------------------------------------------------------------
    avail_resp = client.get(
        f"/api/v1/schedules/doctors/{doctor_id}/availability",
        headers=patient_headers,
    )
    assert avail_resp.status_code == 200
    avail_payload = avail_resp.json()
    assert avail_payload["doctor_id"] == doctor_id
    assert len(avail_payload["schedules"]) >= 1

    tomorrow_item = next((item for item in avail_payload["schedules"] if item["schedule_date"] == str(tomorrow)), None)
    assert tomorrow_item is not None, f"PASS: Tomorrow ({tomorrow}) must appear in schedules"
    assert "09:00 AM – 01:00 PM" in tomorrow_item["formatted_time"]

    # Verify unscheduled date is NOT available
    unsched_item = next((item for item in avail_payload["schedules"] if item["schedule_date"] == str(unscheduled_date)), None)
    assert unsched_item is None, "Unscheduled date must NOT be available"

    # -------------------------------------------------------------------------
    # STEP 12: Select tomorrow -> 09:00 AM – 01:00 PM appears
    # -------------------------------------------------------------------------
    day_doctors_resp = client.get(
        f"/api/v1/schedules/available-doctors?hospital_id={kem_hospital_id}&date={tomorrow}",
        headers=patient_headers,
    )
    assert day_doctors_resp.status_code == 200
    day_doctors = day_doctors_resp.json()["doctors"]
    arjun_day_entry = next((d for d in day_doctors if d["doctor_id"] == doctor_id), None)
    assert arjun_day_entry is not None, "Dr. Arjun Mehta must appear on tomorrow's roster"
    assert "09:00 AM – 01:00 PM" in arjun_day_entry["formatted_time"]

    # -------------------------------------------------------------------------
    # STEP 13: Book an appointment -> Appointment is created
    # First verify booking an unscheduled date is rejected with HTTP 400
    # -------------------------------------------------------------------------
    bad_booking_resp = client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": str(unscheduled_date), "appointment_time": "10:00:00"},
        headers=patient_headers,
    )
    assert bad_booking_resp.status_code == 400, "Backend must reject booking unscheduled date"

    # Book valid tomorrow appointment
    book_resp = client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": str(tomorrow), "appointment_time": "09:30:00"},
        headers=patient_headers,
    )
    assert book_resp.status_code == 201, f"Appointment booking failed: {book_resp.text}"
    patient1_entry = book_resp.json()["entry"]
    assert patient1_entry["appointment_date"] == str(tomorrow)
    assert patient1_entry["token_number"] == 1
    assert "001" in patient1_entry["token_display"]
    entry1_id = patient1_entry["id"]

    # -------------------------------------------------------------------------
    # STEP 14 & 15: Login/open staff queue -> Select tomorrow
    # PASS: Patient appears in the same doctor's queue for tomorrow
    # -------------------------------------------------------------------------
    queue_date_resp = client.get(
        f"/api/v1/queues/{queue_id}/snapshot?queue_date={tomorrow}",
        headers=staff_headers,
    )
    assert queue_date_resp.status_code == 200
    snapshot = queue_date_resp.json()
    waiting_and_booked = snapshot.get("booked_entries", []) + snapshot.get("waiting_entries", [])
    patient1_in_queue = next((e for e in waiting_and_booked if e["id"] == entry1_id), None)
    assert patient1_in_queue is not None, "Patient 1 must appear in tomorrow's staff queue"
    assert patient1_in_queue["token_number"] == 1
    assert patient1_in_queue["appointment_date"] == str(tomorrow)

    # -------------------------------------------------------------------------
    # STEP 16: Add another patient through phone/walk-in
    # PASS: That patient is added to the SAME queue for tomorrow
    # -------------------------------------------------------------------------
    staff_book_payload = {
        "patient_name": "Rohit Patil",
        "patient_phone": "+919820112233",
        "booking_source": "PHONE",
        "priority_class": "NORMAL",
        "appointment_date": str(tomorrow),
        "appointment_time": "10:00:00",
        "notes": "Booked by phone desk",
    }
    phone_book_resp = client.post(
        f"/api/v1/queues/{queue_id}/staff-book",
        json=staff_book_payload,
        headers=staff_headers,
    )
    assert phone_book_resp.status_code == 201, f"Staff phone booking failed: {phone_book_resp.text}"
    patient2_entry = phone_book_resp.json()["entry"]
    assert patient2_entry["appointment_date"] == str(tomorrow)
    assert patient2_entry["booking_source"] == "PHONE"
    assert patient2_entry["queue_id"] == queue_id
    entry2_id = patient2_entry["id"]

    # -------------------------------------------------------------------------
    # STEP 17: Verify token numbers
    # PASS: No duplicate tokens; strictly sequential 1 and 2
    # -------------------------------------------------------------------------
    assert patient1_entry["token_number"] == 1
    assert patient2_entry["token_number"] == 2
    assert patient1_entry["token_number"] != patient2_entry["token_number"], "Tokens must not collide"

    # Re-fetch snapshot and confirm both entries are present in the same queue
    final_snapshot_resp = client.get(
        f"/api/v1/queues/{queue_id}/snapshot?queue_date={tomorrow}",
        headers=staff_headers,
    )
    assert final_snapshot_resp.status_code == 200
    final_entries = (
        final_snapshot_resp.json().get("booked_entries", [])
        + final_snapshot_resp.json().get("waiting_entries", [])
    )
    tokens_in_queue = [e["token_number"] for e in final_entries]
    assert 1 in tokens_in_queue
    assert 2 in tokens_in_queue
    assert len(tokens_in_queue) == len(set(tokens_in_queue)), "No duplicate tokens in queue"

    # -------------------------------------------------------------------------
    # HOSPITAL ISOLATION VERIFICATION:
    # Nair staff cannot schedule KEM's Dr. Arjun Mehta (returns HTTP 403)
    # -------------------------------------------------------------------------
    nair_login_resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "staff.nair@qflow.com", "password": "password123"},
    )
    assert nair_login_resp.status_code == 200
    nair_token = nair_login_resp.json()["access_token"]
    nair_headers = {"Authorization": f"Bearer {nair_token}"}

    cross_hospital_resp = client.post(
        "/api/v1/schedules",
        json={
            "doctor_id": doctor_id,  # KEM doctor
            "department_id": department_id,
            "schedule_date": str(tomorrow + timedelta(days=2)),
            "start_time": "10:00:00",
            "end_time": "14:00:00",
            "status": "AVAILABLE",
        },
        headers=nair_headers,
    )
    assert cross_hospital_resp.status_code == 403, "Staff must be forbidden from scheduling doctors of another hospital"
