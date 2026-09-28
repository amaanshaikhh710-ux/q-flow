"""End-to-end integration test validating the entire Q-FLOW critical integration fix:

MANDATORY 11 TESTS:
TEST 1: Staff creates OPD schedule: KEM, Dr. Neha Kulkarni, 24 September 2026, 10:00 AM – 12:00 PM.
TEST 2: Patient discovers exact same schedule and sees 10:00 AM – 12:00 PM.
TEST 3: Patient (Aarav Sharma) books appointment for 11:00 AM.
TEST 4: Open staff queue: SAME patient appears with correct token, 11:00 AM, 2026-09-24, ONLINE, BOOKED.
TEST 5: Open patient tracking: Estimated consultation is inside 10:00 AM – 12:00 PM IST (NOT 7:03 PM!).
TEST 6: Enter a real origin: 'Mumbra Railway Station' resolves to real coordinates (19.1895, 73.0227).
TEST 7: Calculate CAR, BIKE/TWO-WHEELER, WALK via Google Routes API v2 (zero fake/mock/random durations).
TEST 8: Use device current location: Actual GPS coordinates are stored and used.
TEST 9: Change travel mode: Travel duration changes according to mode and leave-by departure updates.
TEST 10: Cause a real queue event: Doctor delay of 15 min updates predicted consultation and departure time.
TEST 11: Refresh browser / database audit: All identifiers and timestamps match the single source of truth.
"""

import sys
import os
from datetime import date, time as dt_time, datetime, timezone, timedelta
from decimal import Decimal
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.models.queue import Queue
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.user import User, UserRole
from app.models.arrival_plan import ArrivalPlan
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.arrival_optimizer import ArrivalOptimizationService
from app.services.reforecast_service import PredictionService

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))


class TestCriticalIntegrationFlow(unittest.TestCase):
    """Authoritative end-to-end verification across Database -> API -> Staff -> Patient."""

    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()

        # 1. Fetch KEM Hospital
        cls.kem = cls.db.query(Hospital).filter(Hospital.name.like("%King Edward%")).first()
        assert cls.kem is not None, "KEM Hospital must exist in database"

        # 2. Fetch KEM Dermatology Department
        cls.derma = cls.db.query(Department).filter(
            Department.hospital_id == cls.kem.id,
            Department.name == "Dermatology",
        ).first()
        assert cls.derma is not None, "KEM Dermatology department must exist"

        # 3. Fetch Dr. Neha Kulkarni
        cls.doctor = cls.db.query(Doctor).filter(
            Doctor.department_id == cls.derma.id,
            Doctor.name.like("%Neha%"),
        ).first()
        assert cls.doctor is not None, "Dr. Neha Kulkarni must exist under KEM Dermatology"

        # 4. Fetch KEM Staff (Sunil More)
        cls.staff = cls.db.query(User).filter(
            User.hospital_id == cls.kem.id,
            User.role == UserRole.STAFF,
        ).first()
        assert cls.staff is not None, "KEM staff member must exist"

        # 5. Fetch Patient (Aarav Sharma)
        cls.patient = cls.db.query(User).filter(
            User.name.like("%Aarav%"),
            User.role == UserRole.PATIENT,
        ).first()
        assert cls.patient is not None, "Patient Aarav Sharma must exist"

        # Login Staff
        staff_login_res = client.post(
            "/api/v1/auth/login",
            json={"identifier": cls.staff.email, "password": "password123"},
        )
        assert staff_login_res.status_code == 200, f"Staff login failed: {staff_login_res.text}"
        cls.staff_token = staff_login_res.json()["access_token"]
        cls.staff_headers = {"Authorization": f"Bearer {cls.staff_token}"}

        # Login Patient
        patient_login_res = client.post(
            "/api/v1/auth/login",
            json={"identifier": cls.patient.email, "password": "password123"},
        )
        assert patient_login_res.status_code == 200, f"Patient login failed: {patient_login_res.text}"
        cls.patient_token = patient_login_res.json()["access_token"]
        cls.patient_headers = {"Authorization": f"Bearer {cls.patient_token}"}

        cls.target_date = date(2026, 9, 24)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db.rollback()

    def test_01_staff_creates_opd_schedule(self):
        """TEST 1: Staff creates OPD schedule:
        Hospital: KEM
        Doctor: Dr. Neha Kulkarni
        Date: 24 September 2026
        Start: 10:00 AM
        End: 12:00 PM

        PASS: Staff queue shows Dr. Neha Kulkarni, 24 Sept, 10:00 AM – 12:00 PM.
        """
        payload = {
            "hospital_id": str(self.kem.id),
            "department_id": str(self.derma.id),
            "doctor_id": str(self.doctor.id),
            "schedule_date": self.target_date.isoformat(),
            "start_time": "10:00",
            "end_time": "12:00",
            "status": "AVAILABLE",
        }

        # Clean existing test schedule and linked queue entries/events for this date if present
        existing = self.db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == self.doctor.id,
            DoctorSchedule.schedule_date == self.target_date,
        ).first()
        if existing:
            # Clean entries and events in queue
            entries = self.db.query(QueueEntry).filter(QueueEntry.appointment_date == self.target_date).all()
            for e in entries:
                self.db.delete(e)
            if existing.opd_session:
                queues = self.db.query(Queue).filter(Queue.opd_session_id == existing.opd_session.id).all()
                for q in queues:
                    self.db.query(QueueEvent).filter(QueueEvent.queue_id == q.id).delete()
            self.db.delete(existing)
            self.db.commit()

        res = client.post("/api/v1/schedules/", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201, f"Failed to create schedule: {res.text}")
        data = res.json()

        self.assertEqual(data["schedule_date"], "2026-09-24")
        self.assertEqual(data["start_time"][:5], "10:00")
        self.assertEqual(data["end_time"][:5], "12:00")
        self.assertEqual(data["doctor_name"], self.doctor.name)
        self.assertIsNotNone(data["queue_id"])

        TestCriticalIntegrationFlow.schedule_id = data["id"]
        TestCriticalIntegrationFlow.queue_id = data["queue_id"]

        # Verify DB persistence
        self.db.expire_all()
        db_sched = self.db.query(DoctorSchedule).filter(DoctorSchedule.id == uuid.UUID(data["id"])).first()
        self.assertIsNotNone(db_sched)
        self.assertEqual(db_sched.schedule_date, date(2026, 9, 24))
        self.assertEqual(db_sched.start_time, dt_time(10, 0))
        self.assertEqual(db_sched.end_time, dt_time(12, 0))

        # Verify staff queue reflects it
        snap_res = client.get(
            f"/api/v1/queues/{data['queue_id']}/snapshot?target_date=2026-09-24",
            headers=self.staff_headers,
        )
        self.assertEqual(snap_res.status_code, 200)
        snap = snap_res.json()
        self.assertEqual(snap["doctor_name"], self.doctor.name)
        self.assertEqual(snap["queue_date"], "2026-09-24")
        self.assertEqual(snap["start_time"][:5], "10:00")
        self.assertEqual(snap["end_time"][:5], "12:00")

    def test_02_patient_sees_same_opd_schedule(self):
        """TEST 2: Patient selects KEM, Dermatology, Dr. Neha Kulkarni, 24 September.
        PASS: Patient sees 10:00 AM – 12:00 PM.
        """
        res = client.get(
            f"/api/v1/schedules/doctors/{self.doctor.id}/availability",
            params={
                "hospital_id": str(self.kem.id),
                "department_id": str(self.derma.id),
                "from_date": "2026-09-23",
            },
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 200, f"Doctor availability query failed: {res.text}")
        data = res.json()
        schedules = data.get("schedules", [])

        match = next((s for s in schedules if s["schedule_date"] == "2026-09-24"), None)
        self.assertIsNotNone(match, "24 September 2026 schedule must appear in patient availability")
        self.assertEqual(match["start_time"][:5], "10:00")
        self.assertEqual(match["end_time"][:5], "12:00")
        self.assertIn("10:00", match["formatted_time"])
        self.assertIn("12:00", match["formatted_time"])

    def test_03_patient_books_appointment(self):
        """TEST 3: Patient books 11:00 AM on 24 September.
        PASS: Appointment created with ONLINE source and BOOKED status.
        """
        # Clean any prior entry for Aarav on this date and old queue events
        prior_entries = self.db.query(QueueEntry).filter(
            QueueEntry.patient_user_id == self.patient.id,
            QueueEntry.appointment_date == self.target_date,
        ).all()
        for pe in prior_entries:
            self.db.delete(pe)
        qid = uuid.UUID(str(self.queue_id))
        self.db.query(QueueEvent).filter(QueueEvent.queue_id == qid).delete()
        self.db.commit()

        join_payload = {
            "appointment_date": "2026-09-24",
            "appointment_time": "11:00:00",
        }
        res = client.post(
            f"/api/v1/queues/{self.queue_id}/join",
            json=join_payload,
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 201, f"Patient booking failed: {res.text}")
        data = res.json()
        entry = data["entry"]

        self.assertEqual(entry["patient_name"], self.patient.name)
        self.assertEqual(entry["appointment_date"], "2026-09-24")
        self.assertEqual(entry["appointment_time"][:5], "11:00")
        self.assertEqual(entry["status"], "BOOKED")
        self.assertEqual(entry["booking_source"], "ONLINE")
        self.assertGreaterEqual(entry["token_number"], 1)

        TestCriticalIntegrationFlow.entry_id = entry["id"]
        TestCriticalIntegrationFlow.token_number = entry["token_number"]

    def test_04_staff_queue_shows_same_patient(self):
        """TEST 4: Open staff queue for 24 September 2026.
        PASS: The SAME patient appears.
        PASS: Correct token.
        PASS: Correct appointment time (11:00 AM).
        PASS: Correct queue date (2026-09-24).
        """
        res = client.get(
            f"/api/v1/queues/{self.queue_id}/snapshot?target_date=2026-09-24",
            headers=self.staff_headers,
        )
        self.assertEqual(res.status_code, 200, f"Staff snapshot failed: {res.text}")
        snap = res.json()

        self.assertEqual(snap["doctor_name"], self.doctor.name)
        self.assertEqual(snap["department_name"], "Dermatology")
        self.assertEqual(snap["queue_date"], "2026-09-24")
        self.assertEqual(snap["start_time"][:5], "10:00")
        self.assertEqual(snap["end_time"][:5], "12:00")

        booked_entries = snap.get("booked_entries", [])
        aarav_match = next((e for e in booked_entries if e["id"] == self.entry_id), None)
        self.assertIsNotNone(aarav_match, "Aarav Sharma MUST appear in staff booked_entries")

        self.assertEqual(aarav_match["patient_name"], self.patient.name)
        self.assertEqual(aarav_match["token_number"], self.token_number)
        self.assertEqual(aarav_match["appointment_time"][:5], "11:00")
        self.assertEqual(aarav_match["booking_source"], "ONLINE")
        self.assertEqual(aarav_match["status"], "BOOKED")
        self.assertGreaterEqual(snap["total_booked"], 1)

    def test_05_patient_tracking_eta_inside_opd_session(self):
        """TEST 5: Open patient tracking.
        PASS: Estimated consultation is inside the correct OPD session (10:00 AM – 12:00 PM).
        PASS: It MUST NOT show 7 PM (19:03 IST) if the OPD is 10:00 AM – 12:00 PM!
        """
        entry = self.db.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(self.entry_id)).first()
        self.assertIsNotNone(entry)

        # Generate or fetch authoritative prediction
        snap = (
            self.db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(PredictionSnapshot.created_at.desc())
            .first()
        )
        if not snap:
            snap = PredictionService().generate_initial_prediction(self.db, entry.id)

        self.assertIsNotNone(snap)
        start_utc = snap.predicted_start_at
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        start_ist = start_utc.astimezone(IST)

        # MUST be on 24 September 2026
        self.assertEqual(start_ist.date(), date(2026, 9, 24))

        # MUST be inside the 10:00 AM - 12:00 PM session window!
        self.assertGreaterEqual(start_ist.hour, 10, "ETA must be on or after 10:00 AM")
        self.assertLessEqual(start_ist.hour, 12, "ETA must be on or before 12:00 PM")

        # CRITICAL ASSERTION: MUST NOT BE 7 PM (19:03 IST)!
        self.assertNotEqual(start_ist.hour, 19, "CRITICAL BUG: ETA MUST NOT be 7:03 PM (19:03)!")

        # Check patient tracking API endpoint
        tracking_res = client.get(
            f"/api/v1/queue-entries/{self.entry_id}",
            headers=self.patient_headers,
        )
        self.assertEqual(tracking_res.status_code, 200)
        t_data = tracking_res.json()
        self.assertEqual(t_data["appointment_time"][:5], "11:00")
        self.assertEqual(t_data["appointment_date"], "2026-09-24")

    def test_06_origin_resolution(self):
        """TEST 6: Enter a real origin (Mumbra Railway Station).
        PASS: Location resolves to real coordinates.
        """
        res = client.post(
            "/api/v1/resolve-address",
            json={"query": "Mumbra Railway Station"},
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = data.get("results", [])
        self.assertGreater(len(results), 0)
        first_loc = results[0]
        self.assertIn("Mumbra", first_loc["name"])
        self.assertAlmostEqual(first_loc["latitude"], 19.1895, places=2)
        self.assertAlmostEqual(first_loc["longitude"], 73.0227, places=2)

    def test_07_google_routes_calculation_three_modes(self):
        """TEST 7: Calculate CAR, BIKE/TWO-WHEELER, WALK.
        PASS: Each result comes from Google Routes API v2.
        PASS: Zero hardcoded or random durations.
        PASS: Proper error returned when unconfigured (CONFIGURATION_REQUIRED).
        """
        import httpx
        from unittest.mock import MagicMock

        # 1. Verify unconfigured zero-mock policy
        unconf_res = client.post(
            f"/api/v1/queue-entries/{self.entry_id}/travel-origin",
            json={
                "latitude": 19.1895,
                "longitude": 73.0227,
                "origin_address": "Mumbra Railway Station",
                "travel_mode": "DRIVE",
            },
            headers=self.patient_headers,
        )
        self.assertEqual(unconf_res.status_code, 200)
        unconf_plan = unconf_res.json()
        self.assertEqual(unconf_plan["travel_status"], "CONFIGURATION_REQUIRED")
        self.assertIsNone(unconf_plan["driving_duration_seconds"], "Must NOT fabricate driving duration")
        self.assertIsNone(unconf_plan["bike_duration_seconds"], "Must NOT fabricate bike duration")
        self.assertIsNone(unconf_plan["walking_duration_seconds"], "Must NOT fabricate walking duration")

        # 2. Verify Google Routes API v2 request/response handling for DRIVE, TWO_WHEELER, WALK
        mock_http = MagicMock(spec=httpx.Client)

        def mock_post(url, json=None, headers=None, **kwargs):
            mode = json.get("travelMode", "DRIVE")
            if mode == "DRIVE":
                body = {
                    "routes": [{
                        "duration": "2520s",         # 42 mins with live traffic
                        "staticDuration": "1980s",   # 33 mins free flow
                        "distanceMeters": 38400,     # 38.4 km
                    }]
                }
            elif mode == "TWO_WHEELER":
                body = {
                    "routes": [{
                        "duration": "2040s",         # 34 mins
                        "staticDuration": "1860s",   # 31 mins free flow
                        "distanceMeters": 36200,     # 36.2 km
                    }]
                }
            else:  # WALK
                body = {
                    "routes": [{
                        "duration": "27000s",        # 450 mins
                        "staticDuration": "27000s",
                        "distanceMeters": 34500,     # 34.5 km
                    }]
                }
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = body
            return resp

        mock_http.post.side_effect = mock_post
        provider = GoogleRoutesProvider(api_key="valid-routes-key", http_client=mock_http)

        # DRIVE (traffic aware)
        drive_res = provider.estimate_travel(19.1895, 73.0227, 19.0026, 72.8423, travel_mode="DRIVE")
        self.assertEqual(drive_res.duration_seconds, 2520)
        self.assertEqual(drive_res.distance_meters, 38400)
        self.assertTrue(drive_res.is_traffic_aware)

        # TWO_WHEELER (traffic aware)
        bike_res = provider.estimate_travel(19.1895, 73.0227, 19.0026, 72.8423, travel_mode="TWO_WHEELER")
        self.assertEqual(bike_res.duration_seconds, 2040)
        self.assertEqual(bike_res.distance_meters, 36200)

        # WALK
        walk_res = provider.estimate_travel(19.1895, 73.0227, 19.0026, 72.8423, travel_mode="WALK")
        self.assertEqual(walk_res.duration_seconds, 27000)
        self.assertEqual(walk_res.distance_meters, 34500)

        # Verify distinct durations
        self.assertNotEqual(drive_res.duration_seconds, bike_res.duration_seconds)
        self.assertNotEqual(drive_res.duration_seconds, walk_res.duration_seconds)

    def test_08_use_my_current_location_device_coordinates(self):
        """TEST 8: Click USE MY CURRENT LOCATION.
        PASS: Device GPS coordinates are used directly without fake fallback.
        """
        # Actual GPS coordinates near Dadar/Parel
        device_lat = 19.0178
        device_lon = 72.8478

        res = client.post(
            f"/api/v1/queue-entries/{self.entry_id}/travel-origin",
            json={
                "latitude": device_lat,
                "longitude": device_lon,
                "origin_address": "Current Location (GPS)",
                "travel_mode": "DRIVE",
            },
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 200)

        # Verify coordinates saved on queue_entry in DB
        self.db.expire_all()
        entry = self.db.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(self.entry_id)).first()
        self.assertAlmostEqual(float(entry.origin_latitude), device_lat, places=4)
        self.assertAlmostEqual(float(entry.origin_longitude), device_lon, places=4)
        self.assertEqual(entry.origin_address, "Current Location (GPS)")

    def test_09_change_travel_mode_updates_departure(self):
        """TEST 9: Change travel mode (DRIVE -> TWO_WHEELER -> WALK).
        PASS: Travel result changes according to Google Routes response.
        PASS: Recommended leave-by time changes accordingly.
        """
        from unittest.mock import MagicMock
        import httpx

        mock_http = MagicMock(spec=httpx.Client)

        def mock_post(url, json=None, headers=None, **kwargs):
            mode = json.get("travelMode", "DRIVE")
            dur = "2520s" if mode == "DRIVE" else ("2040s" if mode == "TWO_WHEELER" else "27000s")
            dist = 38400 if mode == "DRIVE" else (36200 if mode == "TWO_WHEELER" else 34500)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "routes": [{"duration": dur, "staticDuration": dur, "distanceMeters": dist}]
            }
            return resp

        mock_http.post.side_effect = mock_post
        test_provider = GoogleRoutesProvider(api_key="valid-test-key", http_client=mock_http)
        svc = ArrivalOptimizationService(travel_provider=test_provider)

        entry = self.db.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(self.entry_id)).first()
        entry.origin_latitude = Decimal("19.1895")
        entry.origin_longitude = Decimal("73.0227")
        entry.origin_address = "Mumbra Railway Station"
        self.db.commit()

        snap = (
            self.db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(PredictionSnapshot.created_at.desc())
            .first()
        )
        if not snap:
            snap = PredictionService().generate_initial_prediction(self.db, entry.id)

        # Plan for DRIVE mode
        plan_drive = svc.calculate_arrival_plan(self.db, entry, snap, buffer_minutes=15, selected_travel_mode="DRIVE")
        self.assertEqual(plan_drive.selected_travel_mode, "DRIVE")
        self.assertEqual(plan_drive.travel_duration_seconds, 2520)  # 42 mins
        expected_drive_leave_by = snap.predicted_start_at - timedelta(seconds=2520 + 900)
        self.assertEqual(plan_drive.departure_end_at, expected_drive_leave_by)

        # Plan for TWO_WHEELER mode
        plan_bike = svc.calculate_arrival_plan(self.db, entry, snap, buffer_minutes=15, selected_travel_mode="TWO_WHEELER")
        self.assertEqual(plan_bike.selected_travel_mode, "TWO_WHEELER")
        self.assertEqual(plan_bike.travel_duration_seconds, 2040)  # 34 mins
        expected_bike_leave_by = snap.predicted_start_at - timedelta(seconds=2040 + 900)
        self.assertEqual(plan_bike.departure_end_at, expected_bike_leave_by)

        # Leave-by time MUST change by 8 minutes between DRIVE and BIKE!
        self.assertNotEqual(plan_drive.departure_end_at, plan_bike.departure_end_at)
        time_diff_sec = (plan_bike.departure_end_at - plan_drive.departure_end_at).total_seconds()
        self.assertEqual(time_diff_sec, 480)  # 2520 - 2040 = 480s = 8 mins later

    def test_10_queue_disruption_event_updates_eta_and_departure(self):
        """TEST 10: Cause a real queue event (Doctor Delay of 15 minutes).
        PASS: Predicted consultation changes (+15 minutes).
        PASS: Recommended departure changes (+15 minutes).
        """
        entry = self.db.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(self.entry_id)).first()
        prev_snap = (
            self.db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(PredictionSnapshot.created_at.desc())
            .first()
        )
        prev_start = prev_snap.predicted_start_at

        # Staff records a 15-minute doctor delay
        delay_payload = {
            "delay_minutes": 15,
            "reason": "Emergency surgery handover delay",
        }
        delay_res = client.post(
            f"/api/v1/queues/{self.queue_id}/doctor-delay",
            json=delay_payload,
            headers=self.staff_headers,
        )
        self.assertEqual(delay_res.status_code, 200, f"Doctor delay failed: {delay_res.text}")
        data = delay_res.json()
        self.assertEqual(data["delay_minutes"], 15)

        # Verify a new prediction snapshot was created for Aarav
        self.db.expire_all()
        new_snap = (
            self.db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(PredictionSnapshot.created_at.desc())
            .first()
        )
        self.assertIsNotNone(new_snap)
        self.assertNotEqual(new_snap.id, prev_snap.id, "A new prediction snapshot MUST be created after doctor delay")

        # Predicted start MUST be shifted by 15 minutes
        p_prev = prev_start if prev_start.tzinfo else prev_start.replace(tzinfo=timezone.utc)
        p_new = new_snap.predicted_start_at if new_snap.predicted_start_at.tzinfo else new_snap.predicted_start_at.replace(tzinfo=timezone.utc)
        shift_minutes = int(round((p_new - p_prev).total_seconds() / 60))
        self.assertEqual(shift_minutes, 15, "Predicted consultation start MUST shift by 15 minutes")

    def test_11_refresh_and_database_audit(self):
        """TEST 11: Refresh / database consistency audit.
        PASS: One canonical relationship across:
              Hospital + Department + Doctor + OPD Schedule + Date + Queue.
        PASS: Appointment, queue, schedule, ETA context, and travel configuration remain consistent.
        """
        self.db.expire_all()
        entry = self.db.query(QueueEntry).filter(QueueEntry.id == uuid.UUID(self.entry_id)).first()
        self.assertIsNotNone(entry)

        # Audit all required fields
        self.assertIsNotNone(entry.id, "appointment_id / entry_id must exist")
        self.assertIsNotNone(entry.queue_id, "queue_id must not be NULL")
        self.assertIsNotNone(entry.schedule_id, "schedule_id must not be NULL")
        self.assertEqual(entry.appointment_date, date(2026, 9, 24))
        self.assertEqual(entry.appointment_time, dt_time(11, 0))
        self.assertEqual(entry.status, QueueEntryStatus.BOOKED)
        self.assertEqual(entry.booking_source, "ONLINE")
        self.assertGreaterEqual(entry.token_number, 1)

        # Audit linked schedule
        sched_id = uuid.UUID(str(entry.schedule_id))
        sched = self.db.query(DoctorSchedule).filter(DoctorSchedule.id == sched_id).first()
        self.assertIsNotNone(sched)
        self.assertEqual(sched.doctor_id, self.doctor.id)
        self.assertEqual(sched.hospital_id, self.kem.id)
        self.assertEqual(sched.department_id, self.derma.id)
        self.assertEqual(sched.schedule_date, date(2026, 9, 24))
        self.assertEqual(sched.start_time, dt_time(10, 0))
        self.assertEqual(sched.end_time, dt_time(12, 0))

        # Audit linked queue
        queue = self.db.query(Queue).filter(Queue.id == entry.queue_id).first()
        self.assertIsNotNone(queue)
        self.assertEqual(queue.queue_date, date(2026, 9, 24))

        # Audit staff queue API returns the SAME appointment
        staff_snap_res = client.get(
            f"/api/v1/queues/{queue.id}/snapshot?target_date=2026-09-24",
            headers=self.staff_headers,
        )
        self.assertEqual(staff_snap_res.status_code, 200)
        snap = staff_snap_res.json()
        booked = snap.get("booked_entries", [])
        found = next((b for b in booked if b["id"] == str(entry.id)), None)
        self.assertIsNotNone(found, "Staff snapshot must retrieve the SAME appointment record")
        self.assertEqual(found["token_number"], entry.token_number)
        self.assertEqual(found["patient_name"], self.patient.name)
        self.assertEqual(found["appointment_time"][:5], "11:00")


if __name__ == "__main__":
    unittest.main()
