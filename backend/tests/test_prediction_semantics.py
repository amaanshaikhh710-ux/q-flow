"""Tests for Phase 4.1: Prediction window semantics, uncertainty margins, and non-negativity guarantees."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.schemas.prediction import PredictionResponse
from app.services.prediction_engine import (
    RobustMedianPredictor,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
    MIN_VALID_DURATION_SECONDS,
)
from app.services.reforecast_service import PredictionService
from tests.conftest import make_test_user


def test_prediction_window_chronological_validity(test_client, db_session, seed_opd_data):
    """Verify that predicted_end_at is strictly greater than predicted_start_at and forms a valid window."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Semantics Pat 1", "sem1@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    pred_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()

    start_at = datetime.fromisoformat(data["predicted_start_at"])
    end_at = datetime.fromisoformat(data["predicted_end_at"])

    # Semantics Rule 1: Window must be strictly positive and chronologically ordered
    assert end_at > start_at
    total_window_span = (end_at - start_at).total_seconds()
    assert total_window_span > 0

    # Semantics Rule 2: Window span equals duration + uncertainty margin
    expected_span = data["predicted_duration_seconds"] + data["uncertainty_margin_seconds"]
    assert total_window_span == pytest.approx(expected_span, abs=1.0)


def test_uncertainty_margin_consistency_and_non_negativity():
    """Verify uncertainty margin and duration are strictly positive and consistently represented."""
    predictor = RobustMedianPredictor()

    # Empty history -> safe default
    dur, unc_min, model_type, model_ver, status = predictor.predict_duration({}, [])
    assert dur == SAFE_DEFAULT_DURATION_SECONDS
    assert unc_min == SAFE_DEFAULT_UNCERTAINTY_MINUTES
    assert dur > 0
    assert unc_min > 0

    # Normal history
    dur, unc_min, model_type, model_ver, status = predictor.predict_duration({}, [600, 700, 800, 900, 1000])
    assert dur > 0
    assert unc_min >= 3  # Minimum 3 minutes margin
    margin_seconds = unc_min * 60
    assert margin_seconds >= 180

    # Zero/negative durations are filtered out
    filtered = predictor.filter_valid_durations([-100, 0, 30, 60, 900, 8000])
    assert filtered == [60, 900]
    for d in filtered:
        assert d >= MIN_VALID_DURATION_SECONDS


def test_schema_rejects_negative_duration_or_margin():
    """Verify that PredictionResponse schema enforces ge=0 validation preventing negative durations or margins."""
    now = datetime.now(timezone.utc)
    base_data = {
        "id": uuid.uuid4(),
        "queue_entry_id": uuid.uuid4(),
        "queue_id": uuid.uuid4(),
        "predicted_start_at": now,
        "predicted_end_at": now + timedelta(minutes=20),
        "predicted_duration_seconds": 900,
        "predicted_duration_minutes": 15,
        "uncertainty_margin_seconds": 300,
        "uncertainty_minutes": 5,
        "patients_ahead_count": 2,
        "explanation": "Valid test window",
        "model_type": "robust_median",
        "model_version": "baseline-v1",
        "prediction_status": "VALID",
        "created_at": now,
    }

    # Valid schema instantiation succeeds
    valid_resp = PredictionResponse(**base_data)
    assert valid_resp.predicted_duration_seconds == 900
    assert valid_resp.uncertainty_margin_seconds == 300
    assert valid_resp.patients_ahead_count == 2

    # Negative duration must raise ValidationError
    with pytest.raises(ValidationError):
        invalid_data = dict(base_data, predicted_duration_seconds=-10)
        PredictionResponse(**invalid_data)

    # Negative margin must raise ValidationError
    with pytest.raises(ValidationError):
        invalid_data = dict(base_data, uncertainty_margin_seconds=-60)
        PredictionResponse(**invalid_data)

    # Negative patients ahead count must raise ValidationError
    with pytest.raises(ValidationError):
        invalid_data = dict(base_data, patients_ahead_count=-1)
        PredictionResponse(**invalid_data)


def test_fallback_prediction_has_valid_window_semantics(test_client, db_session, seed_opd_data):
    """Verify cold start fallback prediction has exact expected window semantics."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Fallback Pat", "fallbacksem@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    pred_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()

    assert data["prediction_status"] in ("VALID", "FALLBACK")
    assert 300 <= data["predicted_duration_seconds"] <= 3600
    assert data["uncertainty_minutes"] == SAFE_DEFAULT_UNCERTAINTY_MINUTES
    assert data["uncertainty_margin_seconds"] == SAFE_DEFAULT_UNCERTAINTY_MINUTES * 60

    start_at = datetime.fromisoformat(data["predicted_start_at"])
    end_at = datetime.fromisoformat(data["predicted_end_at"])
    expected_window = data["predicted_duration_seconds"] + data["uncertainty_margin_seconds"]
    assert (end_at - start_at).total_seconds() == pytest.approx(float(expected_window), abs=1.0)


def test_reforecasted_windows_remain_valid_after_disruptions(test_client, db_session, seed_opd_data):
    """Verify that reforecasted windows remain strictly chronologically valid after disruptions."""
    queue = seed_opd_data["queue"]
    staff, s_headers = make_test_user(db_session, "Staff Disrupt", "staffdisrupt@test.com", UserRole.STAFF)
    p1, p1_headers = make_test_user(db_session, "Pat Disrupt 1", "patdis1@test.com", UserRole.PATIENT)
    p2, p2_headers = make_test_user(db_session, "Pat Disrupt 2", "patdis2@test.com", UserRole.PATIENT)

    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p1_headers)
    j2 = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p2_headers)
    e2_id = j2.json()["entry"]["id"]

    p_emerg, _ = make_test_user(db_session, "Emerg Pat", "emergsem@test.com", UserRole.PATIENT)

    # Trigger emergency insertion with valid patient_user_id
    em_res = test_client.post(
        f"/api/v1/queues/{queue.id}/emergency",
        json={"patient_user_id": str(p_emerg.id), "reason": "Immediate triage attention"},
        headers=s_headers,
    )
    assert em_res.status_code == 201

    # Trigger doctor delay
    test_client.post(
        f"/api/v1/queues/{queue.id}/doctor-delay",
        json={"delay_minutes": 25, "reason": "Emergency surgery round"},
        headers=s_headers,
    )


    # Trigger queue reforecast
    ref_res = test_client.post(f"/api/v1/queues/{queue.id}/reforecast", headers=s_headers)
    assert ref_res.status_code == 200

    # Check P2's latest prediction
    pred_res = test_client.get(f"/api/v1/queue-entries/{e2_id}/prediction", headers=p2_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()

    start_at = datetime.fromisoformat(data["predicted_start_at"])
    end_at = datetime.fromisoformat(data["predicted_end_at"])

    # Window remains valid
    assert end_at > start_at
    assert data["predicted_duration_seconds"] > 0
    assert data["uncertainty_margin_seconds"] > 0
    assert data["patients_ahead_count"] >= 2  # P1 + Emergency patient ahead



def test_api_clearly_exposes_required_semantics_without_fake_confidence(test_client, db_session, seed_opd_data):
    """Verify that API exposes all required semantic fields and contains NO fake confidence percentage."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Api Sem Pat", "apisem@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    pred_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()

    # Required fields from prompt
    required_fields = [
        "predicted_start_at",
        "predicted_end_at",
        "uncertainty_margin_seconds",
        "predicted_duration_seconds",
        "patients_ahead_count",
        "explanation",
        "model_version",
    ]
    for field in required_fields:
        assert field in data, f"Required field {field} missing from API response"

    # Verify NO fake confidence percentage field exists
    forbidden_confidence_fields = ["confidence", "confidence_percentage", "confidence_score", "accuracy_percentage"]
    for forbidden in forbidden_confidence_fields:
        assert forbidden not in data, f"Forbidden confidence field '{forbidden}' found in response!"
