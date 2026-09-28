"""Unit tests for Phase 4 baseline predictors, outlier filtering, MAD uncertainty, and fallback hierarchy."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest

from app.models.user import UserRole
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.consultation import Consultation
from app.services.prediction_engine import (
    RobustMedianPredictor,
    SklearnDurationPredictor,
    PredictionFeatureBuilder,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
)
from tests.conftest import make_test_user


def test_robust_median_calculation():
    """Verify median and MAD-based uncertainty calculation on clean historical data."""
    predictor = RobustMedianPredictor()
    # 5 consultations: 600s, 720s, 900s, 960s, 1200s (median = 900s = 15 min)
    durations = [600, 720, 900, 960, 1200]
    pred_sec, unc_min, model_type, model_ver, status = predictor.predict_duration({}, durations)

    assert pred_sec == 900
    assert unc_min >= 3  # MAD is bounded and calculated
    assert model_type == "robust_median"
    assert model_ver == "baseline-v1"
    assert status == "VALID"


def test_outlier_filtering():
    """Verify non-positive and extreme outlier durations are discarded."""
    predictor = RobustMedianPredictor()
    # Contains invalid non-positive (-50, 0) and extreme anomaly (36000s = 10h error)
    durations = [-50, 0, 600, 720, 900, 960, 36000]
    filtered = predictor.filter_valid_durations(durations)

    assert filtered == [600, 720, 900, 960]
    pred_sec, unc_min, _, _, status = predictor.predict_duration({}, durations)
    assert pred_sec == 810  # median of [600, 720, 900, 960]
    assert status == "VALID"


def test_fallback_when_insufficient_data():
    """Verify fallback to safe default when fewer than 3 historical samples exist."""
    predictor = RobustMedianPredictor()
    # Only 2 samples
    durations = [600, 800]
    pred_sec, unc_min, model_type, model_ver, status = predictor.predict_duration({}, durations)

    assert pred_sec == SAFE_DEFAULT_DURATION_SECONDS
    assert unc_min == SAFE_DEFAULT_UNCERTAINTY_MINUTES
    assert status == "FALLBACK"


def test_sklearn_predictor_graceful_degradation():
    """Verify SklearnDurationPredictor falls back seamlessly to baseline when untrained."""
    predictor = SklearnDurationPredictor(model_artifact=None)
    durations = [600, 720, 900, 960, 1200]
    pred_sec, unc_min, model_type, model_ver, status = predictor.predict_duration({}, durations)

    assert pred_sec == 900
    assert model_type == "sklearn_tabular"
    assert status == "FALLBACK"


def test_fallback_hierarchy_tiers(db_session):
    """Verify 5-tier fallback hierarchy in PredictionFeatureBuilder:
    Doctor+Dept Recent -> Doctor Historical -> Dept Historical -> Global -> Safe Default.
    """
    # Setup clinic entities
    hosp = Hospital(name="Hierarchy Hospital")
    db_session.add(hosp)
    db_session.flush()

    dept1 = Department(hospital_id=hosp.id, name="Hierarchy Dept 1")
    dept2 = Department(hospital_id=hosp.id, name="Hierarchy Dept 2")
    db_session.add_all([dept1, dept2])
    db_session.flush()

    doc1 = Doctor(department_id=dept1.id, name="Dr. Hierarchy 1", status=DoctorStatus.AVAILABLE)
    doc2 = Doctor(department_id=dept2.id, name="Dr. Hierarchy 2", status=DoctorStatus.AVAILABLE)
    db_session.add_all([doc1, doc2])
    db_session.flush()

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=60)  # > 30 days old

    # 1. When no consultations exist -> Tier 5 Safe Default
    data, tier = PredictionFeatureBuilder.get_historical_durations(db_session, doc1.id, dept1.id)
    assert tier == "safe_default"
    assert data == []

    # 2. Add old consultations for doc1 in dept1 (older than 30 days)
    # This qualifies for Tier 2 (Doctor Historical), but not Tier 1 (Doctor+Dept Recent)
    sess1 = OPDSession(department_id=dept1.id, doctor_id=doc1.id, starts_at=old_time, status=SessionStatus.COMPLETED)
    db_session.add(sess1)
    db_session.flush()

    q1 = Queue(opd_session_id=sess1.id, name="Q1", status=QueueStatus.COMPLETED)
    db_session.add(q1)
    db_session.flush()

    for i in range(4):
        p, _ = make_test_user(db_session, f"Old P {i}", f"oldp_{i}_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
        qe = QueueEntry(queue_id=q1.id, patient_user_id=p.id, token_number=i+1, status=QueueEntryStatus.COMPLETED, joined_at=old_time)
        db_session.add(qe)
        db_session.flush()

        c = Consultation(
            queue_entry_id=qe.id,
            doctor_id=doc1.id,
            started_at=old_time,
            completed_at=old_time + timedelta(minutes=10),
            duration_seconds=600,
        )
        db_session.add(c)
    db_session.flush()

    # Now doc1 query gives Tier 2 (Doctor historical) because consultations are older than 30 days
    data, tier = PredictionFeatureBuilder.get_historical_durations(db_session, doc1.id, dept1.id)
    assert tier == "doctor_historical"
    assert len(data) == 4

    # 3. Add recent consultations for doc1 in dept1 (within last 5 days) -> Tier 1 (Doctor+Dept recent)
    sess_recent = OPDSession(department_id=dept1.id, doctor_id=doc1.id, starts_at=now, status=SessionStatus.ACTIVE)
    db_session.add(sess_recent)
    db_session.flush()

    q_recent = Queue(opd_session_id=sess_recent.id, name="Q Recent", status=QueueStatus.ACTIVE)
    db_session.add(q_recent)
    db_session.flush()

    for i in range(3):
        p, _ = make_test_user(db_session, f"Rec P {i}", f"recp_{i}_{uuid.uuid4().hex[:6]}@test.com", UserRole.PATIENT)
        qe = QueueEntry(queue_id=q_recent.id, patient_user_id=p.id, token_number=i+10, status=QueueEntryStatus.COMPLETED, joined_at=now)
        db_session.add(qe)
        db_session.flush()

        c = Consultation(
            queue_entry_id=qe.id,
            doctor_id=doc1.id,
            started_at=now - timedelta(minutes=15),
            completed_at=now,
            duration_seconds=900,
        )
        db_session.add(c)
    db_session.flush()

    # Now gives Tier 1
    data, tier = PredictionFeatureBuilder.get_historical_durations(db_session, doc1.id, dept1.id)
    assert tier == "doctor_department_recent"
    assert len(data) >= 3
