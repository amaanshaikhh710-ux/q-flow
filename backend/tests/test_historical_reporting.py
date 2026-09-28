"""Comprehensive test suite for hospital historical reporting, filters, CSV export, and isolation."""

import uuid
from datetime import datetime, timedelta, timezone
from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from tests.conftest import make_test_user


def seed_test_historical_records(db, hospital, dept, doctor, queue, patient):
    """Helper to seed controlled historical entries across dates and statuses."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    last_week = now - timedelta(days=5)

    entries = []

    # 1. Yesterday completed online
    e1 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=1,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.COMPLETED,
        booking_source="ONLINE",
        joined_at=yesterday.replace(hour=9, minute=0, second=0),
        arrived_at=yesterday.replace(hour=9, minute=10, second=0),
    )
    db.add(e1)
    db.flush()
    c1 = Consultation(
        queue_entry_id=e1.id,
        doctor_id=doctor.id,
        started_at=yesterday.replace(hour=9, minute=20, second=0),
        completed_at=yesterday.replace(hour=9, minute=35, second=0),
        duration_seconds=900,
    )
    db.add(c1)
    entries.append(e1)

    # 2. Yesterday no-show phone
    e2 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=2,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.NO_SHOW,
        booking_source="PHONE",
        joined_at=yesterday.replace(hour=10, minute=0, second=0),
    )
    db.add(e2)
    entries.append(e2)

    # 3. Last week completed walk-in
    e3 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=3,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.COMPLETED,
        booking_source="WALK_IN",
        joined_at=last_week.replace(hour=11, minute=0, second=0),
        arrived_at=last_week.replace(hour=11, minute=5, second=0),
    )
    db.add(e3)
    db.flush()
    c3 = Consultation(
        queue_entry_id=e3.id,
        doctor_id=doctor.id,
        started_at=last_week.replace(hour=11, minute=15, second=0),
        completed_at=last_week.replace(hour=11, minute=35, second=0),
        duration_seconds=1200,
    )
    db.add(c3)
    entries.append(e3)

    # 4. Today booked online
    e4 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=4,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.BOOKED,
        booking_source="ONLINE",
        joined_at=now.replace(hour=8, minute=30, second=0),
    )
    db.add(e4)
    entries.append(e4)

    db.commit()
    return entries


def test_historical_reporting_filters_and_export(test_client, db_session, seed_opd_data):
    """Test historical queries across all date presets, filters, pagination, and export."""
    hospital = seed_opd_data["hospital"]
    dept = seed_opd_data["department"]
    doctor = seed_opd_data["doctor"]
    queue = seed_opd_data["queue"]

    # Create staff user scoped to this hospital
    staff_user, s_headers = make_test_user(
        db_session, "Staff Hist", f"staff_hist_{uuid.uuid4().hex[:6]}@hosp.com", UserRole.STAFF, hospital.id
    )
    patient_user, _ = make_test_user(
        db_session, "Pat Hist", f"pat_hist_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT
    )

    # Seed test entries
    seed_test_historical_records(db_session, hospital, dept, doctor, queue, patient_user)

    # 1. Filter: Today
    res_today = test_client.get(
        "/api/v1/hospital/historical-appointments?date_preset=today",
        headers=s_headers,
    )
    assert res_today.status_code == 200
    data_today = res_today.json()
    assert data_today["total_count"] >= 1
    assert all(item["date"].startswith(datetime.now(timezone.utc).strftime("%Y-%m-%d")) for item in data_today["items"])

    # 2. Filter: Yesterday
    res_yest = test_client.get(
        "/api/v1/hospital/historical-appointments?date_preset=yesterday",
        headers=s_headers,
    )
    assert res_yest.status_code == 200
    data_yest = res_yest.json()
    assert data_yest["total_count"] == 2
    assert any(item["status"] == "COMPLETED" for item in data_yest["items"])
    assert any(item["status"] == "NO_SHOW" for item in data_yest["items"])

    # 3. Filter: Last Week
    res_last_week = test_client.get(
        "/api/v1/hospital/historical-appointments?date_preset=last_week",
        headers=s_headers,
    )
    assert res_last_week.status_code == 200

    # 4. Filter: Status = COMPLETED
    res_comp = test_client.get(
        "/api/v1/hospital/historical-appointments?status=COMPLETED",
        headers=s_headers,
    )
    assert res_comp.status_code == 200
    assert all(item["status"] == "COMPLETED" for item in res_comp.json()["items"])

    # 5. Filter: Booking Source = ONLINE
    res_online = test_client.get(
        "/api/v1/hospital/historical-appointments?booking_source=ONLINE",
        headers=s_headers,
    )
    assert res_online.status_code == 200
    assert all(item["booking_source"] == "ONLINE" for item in res_online.json()["items"])

    # 6. Filter: Doctor ID
    res_doc = test_client.get(
        f"/api/v1/hospital/historical-appointments?doctor_id={doctor.id}",
        headers=s_headers,
    )
    assert res_doc.status_code == 200
    assert all(item["doctor_id"] == str(doctor.id) for item in res_doc.json()["items"])

    # 7. Filter: Combined (Yesterday + Completed + Online)
    res_combined = test_client.get(
        f"/api/v1/hospital/historical-appointments?date_preset=yesterday&status=COMPLETED&booking_source=ONLINE",
        headers=s_headers,
    )
    assert res_combined.status_code == 200
    assert res_combined.json()["total_count"] == 1
    assert res_combined.json()["items"][0]["token_number"] == 1
    assert res_combined.json()["items"][0]["consultation_duration_minutes"] == 15.0

    # 8. Pagination (page_size = 2)
    res_page = test_client.get(
        "/api/v1/hospital/historical-appointments?page=1&page_size=2",
        headers=s_headers,
    )
    assert res_page.status_code == 200
    assert len(res_page.json()["items"]) <= 2
    assert res_page.json()["page_size"] == 2

    # 9. CSV Export
    res_export = test_client.get(
        "/api/v1/hospital/historical-appointments/export?date_preset=yesterday",
        headers=s_headers,
    )
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")
    assert "attachment" in res_export.headers.get("content-disposition", "")
    csv_text = res_export.text
    assert "Token Number,Date,Booking Source" in csv_text
    assert "ONLINE" in csv_text or "PHONE" in csv_text


def test_cross_hospital_historical_isolation(test_client, db_session, seed_opd_data):
    """Test that staff of Hospital A cannot retrieve or export Hospital B historical records."""
    hosp_a = seed_opd_data["hospital"]

    # Create Hospital B
    hosp_b = Hospital(name="Hospital B Other", address="456 Other Rd")
    db_session.add(hosp_b)
    db_session.commit()

    # Staff A belongs to Hospital A
    staff_a, s_headers_a = make_test_user(
        db_session, "Staff A", f"staff_a_{uuid.uuid4().hex[:6]}@hosp.com", UserRole.STAFF, hosp_a.id
    )
    # Staff B belongs to Hospital B
    staff_b, s_headers_b = make_test_user(
        db_session, "Staff B", f"staff_b_{uuid.uuid4().hex[:6]}@hosp.com", UserRole.STAFF, hosp_b.id
    )

    # Staff B queries historical records -> gets 0 records from Hospital A
    res_b = test_client.get("/api/v1/hospital/historical-appointments", headers=s_headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["total_count"] == 0

    # Patient attempts to access staff historical endpoint -> 403 Forbidden
    patient, p_headers = make_test_user(
        db_session, "Patient Unauthorized", f"pat_unauth_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT
    )
    res_pat = test_client.get("/api/v1/hospital/historical-appointments", headers=p_headers)
    assert res_pat.status_code == 403

    # Unauthenticated -> 401 Unauthorized
    res_unauth = test_client.get("/api/v1/hospital/historical-appointments")
    assert res_unauth.status_code == 401
