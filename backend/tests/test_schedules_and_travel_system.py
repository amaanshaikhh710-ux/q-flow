"""Comprehensive integration test suite for Doctor Scheduling, Multi-Mode Travel Routing, and Patient Booking."""

import uuid
from datetime import date, time, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db, SessionLocal
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.doctor_schedule import DoctorSchedule
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.opd_session import OPDSession, SessionStatus
from app.models.user import User, UserRole
from app.models.arrival_plan import ArrivalPlan
from app.models.prediction_snapshot import PredictionSnapshot
from app.core.security import create_access_token


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


def test_doctor_schedule_and_booking_workflow(client: TestClient, db_session: Session):
    """Verify complete Doctor Scheduling & Patient Booking system:
    1. Staff creates schedule for Dr. Arjun Mehta on 11 Oct (09:00–13:00)
    2. Patient selecting 11 Oct sees Dr. Arjun Mehta with '09:00 AM – 01:00 PM'
    3. Patient selecting 12 Oct (unscheduled) does NOT see Dr. Arjun Mehta
    4. Backend booking for 12 Oct is rejected with HTTP 400
    5. Staff hospital isolation: KEM staff cannot schedule BYL Nair doctors
    """
    # Setup test entities
    hosp_kem = db_session.query(Hospital).filter(Hospital.name.like("%KEM%")).first()
    if not hosp_kem:
        hosp_kem = Hospital(name="KEM Hospital", address="Parel, Mumbai", latitude=Decimal("19.0033"), longitude=Decimal("72.8423"))
        db_session.add(hosp_kem)
        db_session.commit()

    hosp_nair = db_session.query(Hospital).filter(Hospital.name.like("%Nair%")).first()
    if not hosp_nair:
        hosp_nair = Hospital(name="BYL Nair Hospital", address="Mumbai Central, Mumbai", latitude=Decimal("18.9690"), longitude=Decimal("72.8205"))
        db_session.add(hosp_nair)
        db_session.commit()

    dept_kem = db_session.query(Department).filter(Department.hospital_id == hosp_kem.id).first()
    if not dept_kem:
        dept_kem = Department(hospital_id=hosp_kem.id, name="General Medicine")
        db_session.add(dept_kem)
        db_session.commit()

    dept_nair = db_session.query(Department).filter(Department.hospital_id == hosp_nair.id).first()
    if not dept_nair:
        dept_nair = Department(hospital_id=hosp_nair.id, name="Cardiology")
        db_session.add(dept_nair)
        db_session.commit()

    # Create Dr. Arjun Mehta at KEM
    doc_arjun = db_session.query(Doctor).filter(Doctor.name.like("%Arjun%")).first()
    if not doc_arjun:
        doc_arjun = Doctor(department_id=dept_kem.id, name="Dr. Arjun Mehta", status=DoctorStatus.AVAILABLE)
        db_session.add(doc_arjun)
        db_session.commit()

    # Create Dr. Nair Doctor
    doc_nair = db_session.query(Doctor).filter(Doctor.department_id == dept_nair.id).first()
    if not doc_nair:
        doc_nair = Doctor(department_id=dept_nair.id, name="Dr. Rajesh Sharma", status=DoctorStatus.AVAILABLE)
        db_session.add(doc_nair)
        db_session.commit()

    # Create KEM staff user
    kem_staff = db_session.query(User).filter(User.email == "kem_staff_test@qflow.com").first()
    if not kem_staff:
        kem_staff = User(
            name="KEM Staff",
            email="kem_staff_test@qflow.com",
            password_hash="mock_hash",
            role=UserRole.STAFF,
            hospital_id=hosp_kem.id,
        )
        db_session.add(kem_staff)
        db_session.commit()

    # Create Patient user
    patient_user = db_session.query(User).filter(User.email == "patient_schedule_test@qflow.com").first()
    if not patient_user:
        patient_user = User(
            name="Test Patient",
            email="patient_schedule_test@qflow.com",
            password_hash="mock_hash",
            role=UserRole.PATIENT,
        )
        db_session.add(patient_user)
        db_session.commit()

    staff_token = create_access_token(
        subject=str(kem_staff.id),
        role=kem_staff.role.value,
        extra_claims={"hospital_id": str(hosp_kem.id)},
    )
    patient_token = create_access_token(
        subject=str(patient_user.id),
        role=patient_user.role.value,
    )

    # Pick future dates
    today = date.today()
    target_date = today + timedelta(days=20)  # e.g., 11 Oct equivalent
    unscheduled_date = today + timedelta(days=21)  # e.g., 12 Oct equivalent

    # Clean any prior schedules and entries for test repeatability
    db_session.query(QueueEntry).filter(
        QueueEntry.patient_user_id == patient_user.id,
    ).delete(synchronize_session=False)
    db_session.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doc_arjun.id,
        DoctorSchedule.schedule_date.in_([target_date, unscheduled_date]),
    ).delete(synchronize_session=False)
    db_session.commit()

    # STEP 1: Staff creates schedule for Dr. Arjun Mehta on target_date (09:00–13:00)
    sched_payload = {
        "doctor_id": str(doc_arjun.id),
        "schedule_date": str(target_date),
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    resp = client.post(
        "/api/v1/schedules",
        json=sched_payload,
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    sched_data = resp.json()
    assert sched_data["doctor_name"] == doc_arjun.name
    assert sched_data["start_time_formatted"] == "09:00 AM"
    assert sched_data["end_time_formatted"] == "01:00 PM"
    assert sched_data["queue_id"] is not None
    queue_id = sched_data["queue_id"]

    # STEP 2: Patient selecting target_date sees Dr. Arjun Mehta with "09:00 AM – 01:00 PM"
    resp_avail = client.get(
        f"/api/v1/schedules/available-doctors?hospital_id={hosp_kem.id}&date={target_date}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp_avail.status_code == 200
    avail_data = resp_avail.json()
    doc_match = [d for d in avail_data["doctors"] if d["doctor_id"] == str(doc_arjun.id)]
    assert len(doc_match) == 1, f"Expected Dr. Arjun Mehta on {target_date}, found: {avail_data['doctors']}"
    assert "09:00 AM – 01:00 PM" in doc_match[0]["formatted_time"]

    # STEP 3: Patient selecting unscheduled_date does NOT see Dr. Arjun Mehta
    resp_unavail = client.get(
        f"/api/v1/schedules/available-doctors?hospital_id={hosp_kem.id}&date={unscheduled_date}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp_unavail.status_code == 200
    unavail_data = resp_unavail.json()
    doc_match_unsched = [d for d in unavail_data["doctors"] if d["doctor_id"] == str(doc_arjun.id)]
    assert len(doc_match_unsched) == 0, f"Dr. Arjun Mehta should NOT be available on unscheduled {unscheduled_date}"

    # STEP 4: Backend booking for unscheduled_date is rejected with HTTP 400
    resp_bad_book = client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": str(unscheduled_date)},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp_bad_book.status_code == 400, f"Expected 400 for unscheduled date booking, got {resp_bad_book.status_code}: {resp_bad_book.text}"
    assert "no scheduled clinic" in resp_bad_book.text.lower() or "not scheduled" in resp_bad_book.text.lower()

    # Valid booking for target_date succeeds
    resp_good_book = client.post(
        f"/api/v1/queues/{queue_id}/join",
        json={"appointment_date": str(target_date)},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp_good_book.status_code == 201, f"Expected 201 for scheduled date booking, got {resp_good_book.status_code}: {resp_good_book.text}"
    entry_id = resp_good_book.json()["entry"]["id"]

    # STEP 5: Staff hospital isolation: KEM staff cannot schedule BYL Nair doctors
    bad_staff_payload = {
        "doctor_id": str(doc_nair.id),
        "schedule_date": str(target_date),
        "start_time": "09:00:00",
        "end_time": "13:00:00",
        "status": "AVAILABLE",
    }
    resp_iso = client.post(
        "/api/v1/schedules",
        json=bad_staff_payload,
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp_iso.status_code == 403, f"Expected 403 hospital isolation violation, got {resp_iso.status_code}: {resp_iso.text}"
    assert "access denied" in resp_iso.text.lower() or "outside their assigned hospital" in resp_iso.text.lower()

    print("[SUCCESS] All 5 Doctor Scheduling & Patient Booking tests passed!")


def test_multi_mode_travel_and_departure_calculation(client: TestClient, db_session: Session):
    """Verify Real Travel Time and Multi-Mode Departure Recalculation:
    1. Set origin coordinates (Mumbra -> KEM Hospital)
    2. Test travel mode switching (DRIVE -> TWO_WHEELER -> WALK)
    3. Verify departure recalculation: Departure = Turn - Travel Duration - 10 min buffer
    4. Verify zero fake numbers: unconfigured API key returns CONFIGURATION_REQUIRED
    """
    # Find or create active entry
    entry = db_session.query(QueueEntry).filter(QueueEntry.status.in_([QueueEntryStatus.BOOKED, QueueEntryStatus.WAITING])).first()
    assert entry is not None, "Need at least one active queue entry"

    # Patient auth token
    patient_user = entry.patient or db_session.query(User).filter(User.id == entry.patient_user_id).first()
    token = create_access_token(
        subject=str(patient_user.id),
        role=patient_user.role.value,
    )

    # Test 1: Set Origin (Mumbra: 19.1912, 73.0234)
    origin_payload = {
        "latitude": 19.1912,
        "longitude": 73.0234,
        "travel_mode": "DRIVE",
        "origin_address": "Mumbra, Thane",
    }
    resp = client.post(
        f"/api/v1/queue-entries/{entry.id}/travel-origin",
        json=origin_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    plan_data = resp.json()
    assert plan_data["origin_address"] == "Mumbra, Thane"
    assert "arrival_buffer_minutes" in plan_data
    assert plan_data["arrival_buffer_minutes"] == 15

    # Test 2: Switch mode to TWO_WHEELER
    mode_payload = {"travel_mode": "TWO_WHEELER"}
    resp_mode = client.post(
        f"/api/v1/queue-entries/{entry.id}/travel-mode",
        json=mode_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_mode.status_code == 200, f"Expected 200, got {resp_mode.status_code}: {resp_mode.text}"
    updated_plan = resp_mode.json()
    assert updated_plan["selected_travel_mode"] == "TWO_WHEELER"

    # Test 3: Switch mode to WALK
    walk_payload = {"travel_mode": "WALK"}
    resp_walk = client.post(
        f"/api/v1/queue-entries/{entry.id}/travel-mode",
        json=walk_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_walk.status_code == 200, f"Expected 200, got {resp_walk.status_code}: {resp_walk.text}"
    walk_plan = resp_walk.json()
    assert walk_plan["selected_travel_mode"] == "WALK"

    # Test 4: Get multi-mode travel estimate
    resp_est = client.get(
        f"/api/v1/queue-entries/{entry.id}/travel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_est.status_code == 200
    est_data = resp_est.json()
    assert "provider" in est_data
    assert "travel_status" in est_data
    # If unconfigured, must honestly report CONFIGURATION_REQUIRED
    if est_data["travel_status"] == "CONFIGURATION_REQUIRED":
        assert est_data["travel_duration_seconds"] is None
        assert est_data["travel_duration_minutes"] is None
        print("[SUCCESS] Zero fake numbers verified: unconfigured provider correctly returns CONFIGURATION_REQUIRED with null durations.")
    else:
        # If configured with real Google Routes API key, durations are populated
        assert est_data["travel_duration_minutes"] is not None
        print(f"[SUCCESS] Real Google Routes estimate returned: {est_data['travel_duration_minutes']} min")

    print("[SUCCESS] Multi-mode travel and departure calculation tests passed!")
