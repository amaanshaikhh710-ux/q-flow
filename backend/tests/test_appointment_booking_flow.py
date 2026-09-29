"""Comprehensive verification tests for the appointment booking flow, queue resolution,
and resilience against stale/invalid queue IDs.
"""

import uuid
from datetime import date, time, timedelta, datetime, timezone
import pytest
from app.models.user import UserRole
from app.models.doctor import Doctor
from app.models.department import Department
from app.models.hospital import Hospital
from app.models.doctor_schedule import DoctorSchedule
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.services.seed_service import seed_demo_data
from tests.conftest import make_test_user


def test_doctor_rohan_deshpande_booking_with_stale_or_missing_queue_id(test_client, db_session):
    """Test the exact scenario reported by the user:
    - Doctor: Dr. Rohan Deshpande
    - Target Date: 30 September 2026
    - Selected Slot: 11:00 AM
    - Client sends an arbitrary/stale/non-existent Queue ID: ecf0c6f8-0431-48f4-a25c-b5d7a7ff7ffc
    - Backend MUST resolve or provision the correct queue and successfully book the appointment!
    """
    # 1. Run idempotent seed
    seed_demo_data(db_session)
    db_session.commit()

    # 2. Authenticate patient
    patient, p_headers = make_test_user(
        db_session, "Booking Test Patient", "bookingpatient@test.com", UserRole.PATIENT
    )

    # 3. Locate Dr. Rohan Deshpande
    rohan = db_session.query(Doctor).filter(Doctor.name.ilike("%Rohan Deshpande%")).first()
    assert rohan is not None, "Dr. Rohan Deshpande must be present in database"
    dept = rohan.department
    hosp = dept.hospital

    # 4. Query Doctor Availability endpoint for 30 September 2026
    target_date = date(2026, 9, 30)
    avail_res = test_client.get(
        f"/api/v1/schedules/doctors/{rohan.id}/availability",
        params={
            "hospital_id": str(hosp.id),
            "department_id": str(dept.id),
            "from_date": target_date.isoformat(),
        },
        headers=p_headers,
    )
    assert avail_res.status_code == 200, f"Availability check failed: {avail_res.text}"
    avail_data = avail_res.json()
    assert len(avail_data["schedules"]) > 0

    sched_item = next(
        (s for s in avail_data["schedules"] if s["schedule_date"] == target_date.isoformat()),
        avail_data["schedules"][0]
    )
    actual_sched_date = sched_item["schedule_date"]

    # 5. Simulate the exact reported error: Frontend sends stale Queue ID
    stale_queue_id = "ecf0c6f8-0431-48f4-a25c-b5d7a7ff7ffc"

    # Call /queues/{queue_id}/join with stale queue ID but with doctor_id & date
    join_res = test_client.post(
        f"/api/v1/queues/{stale_queue_id}/join",
        json={
            "appointment_date": actual_sched_date,
            "appointment_time": "11:00:00",
            "doctor_id": str(rohan.id),
            "hospital_id": str(hosp.id),
            "department_id": str(dept.id),
        },
        headers=p_headers,
    )
    assert join_res.status_code == 201, f"Booking with stale queue ID failed: {join_res.text}"
    entry_data = join_res.json()["entry"]
    assert entry_data["appointment_date"] == actual_sched_date
    assert entry_data["appointment_time"].startswith("11:00")
    assert entry_data["status"] == "BOOKED"

    # 6. Verify entry in database
    entry_id = uuid.UUID(entry_data["id"])
    db_entry = db_session.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    assert db_entry is not None
    assert db_entry.patient_user_id == patient.id
    assert db_entry.appointment_date == date.fromisoformat(actual_sched_date)
    assert db_entry.appointment_time == time(11, 0, 0)
    assert db_entry.queue.opd_session.doctor_id == rohan.id
    assert db_entry.queue.opd_session.department.hospital_id == hosp.id

    # 7. Check Patient Appointments endpoint persists it
    my_res = test_client.get("/api/v1/queue-entries/my", headers=p_headers)
    assert my_res.status_code == 200
    my_data = my_res.json()
    all_appts = my_data["today"] + my_data["upcoming"] + my_data["past"]
    assert any(a["id"] == str(entry_id) for a in all_appts)


def test_dedicated_book_appointment_endpoint(test_client, db_session):
    """Test the first-class POST /api/v1/queues/book endpoint without requiring queue_id."""
    seed_demo_data(db_session)
    db_session.commit()

    patient, p_headers = make_test_user(
        db_session, "Book API Patient", "bookapipatient@test.com", UserRole.PATIENT
    )

    doctor = db_session.query(Doctor).first()
    assert doctor is not None
    target_date = date.today() + timedelta(days=2)

    res = test_client.post(
        "/api/v1/queues/book",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": target_date.isoformat(),
            "appointment_time": "10:30:00",
            "hospital_id": str(doctor.department.hospital_id),
            "department_id": str(doctor.department_id),
        },
        headers=p_headers,
    )
    assert res.status_code == 201, f"Book endpoint failed: {res.text}"
    entry = res.json()["entry"]
    assert entry["appointment_date"] == target_date.isoformat()
    assert entry["appointment_time"].startswith("10:30")
    assert entry["status"] == "BOOKED"


def test_duplicate_appointment_booking_rejection(test_client, db_session):
    """Verify that a patient cannot book duplicate appointments for the same doctor/shift."""
    seed_demo_data(db_session)
    db_session.commit()

    patient, p_headers = make_test_user(
        db_session, "Dup Patient", "duppatient@test.com", UserRole.PATIENT
    )

    doctor = db_session.query(Doctor).first()
    target_date = date.today() + timedelta(days=3)

    # First booking -> 201
    res1 = test_client.post(
        "/api/v1/queues/book",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": target_date.isoformat(),
            "appointment_time": "09:30:00",
        },
        headers=p_headers,
    )
    assert res1.status_code == 201

    # Second booking for same doctor & date -> 409 Conflict
    res2 = test_client.post(
        "/api/v1/queues/book",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": target_date.isoformat(),
            "appointment_time": "14:00:00",
        },
        headers=p_headers,
    )
    assert res2.status_code == 409
    assert "already has an active ticket" in res2.json()["detail"]


def test_booking_slot_outside_shift_rejection(test_client, db_session):
    """Verify that an appointment time outside the doctor's shift (09:00 - 17:00) is rejected."""
    seed_demo_data(db_session)
    db_session.commit()

    patient, p_headers = make_test_user(
        db_session, "Outside Shift Patient", "outsideshift@test.com", UserRole.PATIENT
    )

    doctor = db_session.query(Doctor).first()
    target_date = date.today() + timedelta(days=1)

    # Time before 09:00 (e.g. 08:00) -> 400
    res_early = test_client.post(
        "/api/v1/queues/book",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": target_date.isoformat(),
            "appointment_time": "08:00:00",
        },
        headers=p_headers,
    )
    assert res_early.status_code == 400
    assert "outside the doctor's scheduled shift" in res_early.json()["detail"]

    # Time after 17:00 (e.g. 18:00) -> 400
    res_late = test_client.post(
        "/api/v1/queues/book",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": target_date.isoformat(),
            "appointment_time": "18:00:00",
        },
        headers=p_headers,
    )
    assert res_late.status_code == 400
    assert "outside the doctor's scheduled shift" in res_late.json()["detail"]
