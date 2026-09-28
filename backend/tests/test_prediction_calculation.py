"""Unit and service tests for consultation start-time calculations, active consultation progress, and disruption adjustments."""

import uuid
from datetime import datetime, timezone, timedelta, date, time as dt_time
import pytest

from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.services.prediction_engine import RobustMedianPredictor
from app.services.reforecast_service import PredictionService
from app.services.reforecast_service import IST
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from tests.conftest import make_test_user


def test_initial_prediction_on_join(db_session, seed_opd_data):
    """Verify initial prediction snapshot is created on join with honest uncertainty window."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Pred Pat 1", "predpat1@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    prediction_service = PredictionService()
    snapshot = prediction_service.generate_initial_prediction(db_session, entry.id)

    assert snapshot is not None
    assert snapshot.queue_entry_id == entry.id
    assert snapshot.queue_id == queue.id
    assert snapshot.predicted_start_at is not None
    assert snapshot.predicted_end_at > snapshot.predicted_start_at
    assert snapshot.uncertainty_minutes >= 3
    assert "Initial estimate" in snapshot.explanation_text
    assert snapshot.is_meaningful_change is False


def test_waiting_patients_ahead_calculation(db_session, seed_opd_data):
    """Verify expected start times scale with the number of patients ahead in authoritative queue order."""
    queue = seed_opd_data["queue"]
    p1, _ = make_test_user(db_session, "P Ahead 1", "pahead1@test.com", UserRole.PATIENT)
    p2, _ = make_test_user(db_session, "P Ahead 2", "pahead2@test.com", UserRole.PATIENT)
    p3, _ = make_test_user(db_session, "P Ahead 3", "pahead3@test.com", UserRole.PATIENT)

    e1 = QueueEngineService.join_queue(db_session, queue.id, p1.id)
    e2 = QueueEngineService.join_queue(db_session, queue.id, p2.id)
    e3 = QueueEngineService.join_queue(db_session, queue.id, p3.id)

    prediction_service = PredictionService()
    calc1 = prediction_service.calculate_entry_prediction(db_session, e1)
    calc2 = prediction_service.calculate_entry_prediction(db_session, e2)
    calc3 = prediction_service.calculate_entry_prediction(db_session, e3)

    assert calc1["features"]["patients_ahead"] == 0
    assert calc2["features"]["patients_ahead"] == 1
    assert calc3["features"]["patients_ahead"] == 2

    # e2 start should be approximately e1 start + duration
    diff_sec_1_2 = (calc2["predicted_start_at"] - calc1["predicted_start_at"]).total_seconds()
    assert abs(diff_sec_1_2 - calc1["predicted_duration_seconds"]) < 5

    # e3 start should be approximately e2 start + duration
    diff_sec_2_3 = (calc3["predicted_start_at"] - calc2["predicted_start_at"]).total_seconds()
    assert abs(diff_sec_2_3 - calc2["predicted_duration_seconds"]) < 5


def test_active_consultation_elapsed_subtraction(db_session, seed_opd_data):
    """Verify in-progress consultation subtracts elapsed time from remaining duration."""
    queue = seed_opd_data["queue"]
    p_active, _ = make_test_user(db_session, "Active Pat", "activepat@test.com", UserRole.PATIENT)
    p_waiting, _ = make_test_user(db_session, "Waiting Pat", "waitpat@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Active", "staffact@test.com", UserRole.STAFF)

    e_active = QueueEngineService.join_queue(db_session, queue.id, p_active.id)
    e_waiting = QueueEngineService.join_queue(db_session, queue.id, p_waiting.id)

    # Start consultation 10 minutes ago
    QueueStateMachineService.call_patient(db_session, e_active.id, staff.id)
    consultation = QueueStateMachineService.start_consultation(db_session, e_active.id, staff.id)

    # Backdate started_at by 10 minutes (600s)
    now = datetime.now(timezone.utc)
    consultation.started_at = now - timedelta(minutes=10)
    db_session.commit()

    prediction_service = PredictionService()
    calc_wait = prediction_service.calculate_entry_prediction(db_session, e_waiting)

    # Default duration is 900s; with 600s elapsed, remaining should be ~300s (5 min)
    expected_remaining = max(60, calc_wait["predicted_duration_seconds"] - 600)
    diff_to_now = (calc_wait["predicted_start_at"] - now).total_seconds()
    assert abs(diff_to_now - expected_remaining) < 5


def test_doctor_delay_and_break_impact(db_session, seed_opd_data):
    """Verify doctor operational delays and breaks adjust expected start times."""
    queue = seed_opd_data["queue"]
    p, _ = make_test_user(db_session, "Delay Pat", "delaypat@test.com", UserRole.PATIENT)
    staff, _ = make_test_user(db_session, "Staff Delay", "staffdel@test.com", UserRole.STAFF)

    entry = QueueEngineService.join_queue(db_session, queue.id, p.id)

    prediction_service = PredictionService()
    calc_before = prediction_service.calculate_entry_prediction(db_session, entry)

    # Staff records 25-minute doctor delay
    QueueStateMachineService.record_doctor_delay(
        db_session, queue.id, delay_minutes=25, actor_id=staff.id, reason="Emergency surgery"
    )

    calc_after = prediction_service.calculate_entry_prediction(db_session, entry)
    shift_seconds = (calc_after["predicted_start_at"] - calc_before["predicted_start_at"]).total_seconds()

    # Should shift later by 25 minutes = 1500 seconds
    assert abs(shift_seconds - 1500) < 5


def test_graceful_degradation_on_prediction_error(db_session, seed_opd_data):
    """Verify that if prediction generation raises an error, queue join succeeds and error is safely isolated."""
    queue = seed_opd_data["queue"]
    p, _ = make_test_user(db_session, "Degrade Pat", "degradepat@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, p.id)
    assert entry.status == QueueEntryStatus.WAITING

    # Create mock predictor that throws exception
    class BrokenPredictor(RobustMedianPredictor):
        def predict_duration(self, *args, **kwargs):
            raise RuntimeError("Simulated ML engine crash")

    broken_service = PredictionService(predictor=BrokenPredictor())
    snapshot = broken_service.generate_initial_prediction(db_session, entry.id)

    # Prediction snapshot returns None gracefully without crashing or rolling back queue entry
    assert snapshot is None
    db_entry = db_session.query(QueueEntry).filter(QueueEntry.id == entry.id).first()
    assert db_entry is not None
    assert db_entry.status == QueueEntryStatus.WAITING


def test_initial_prediction_on_staff_booking_anchor_date(db_session, seed_opd_data):
    """Staff-booked appointment must generate initial snapshot anchored to booked date/time."""
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Booker", "staffbook@test.com", UserRole.STAFF)

    # Book for the queue's date with explicit time
    appointment_date = queue.queue_date
    appointment_time = dt_time(9, 0)

    entry = QueueEngineService.staff_book_appointment(
        db_session,
        queue_id=queue.id,
        staff_user_id=staff.id,
        patient_name="Booked Pat",
        patient_phone=None,
        booking_source="STAFF",
        appointment_date=appointment_date,
        appointment_time=appointment_time,
    )

    prediction_service = PredictionService()
    snapshot = prediction_service.generate_initial_prediction(db_session, entry.id)

    assert snapshot is not None
    # stored UTC -> convert to IST for comparison
    predicted_ist = snapshot.predicted_start_at.astimezone(IST)
    assert predicted_ist.date() == appointment_date
    # Predicted time must be at or after the booked slot (queue progress or delays may move it later)
    assert (predicted_ist.time() >= appointment_time)
