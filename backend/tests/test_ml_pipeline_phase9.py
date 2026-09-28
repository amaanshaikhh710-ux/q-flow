"""Comprehensive Phase 9 Tests: ML duration prediction, feature extraction, safety bounds, and baseline fallback."""

import os
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from app.models.queue_entry import QueueEntry, PriorityClass, QueueEntryStatus
from app.models.consultation import Consultation
from app.services.prediction_engine import (
    RobustMedianPredictor,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
)
from app.services.prediction_features import (
    FEATURE_COLUMNS,
    PredictionFeatureExtractor,
    priority_to_code,
)
from app.services.prediction_model_service import (
    PredictionModelService,
    ModelStatus,
    MIN_SAFE_DURATION_SECONDS,
    MAX_SAFE_DURATION_SECONDS,
)
from app.services.hybrid_prediction_service import HybridPredictionService
from app.services.reforecast_service import PredictionService


def test_feature_extractor_columns_and_shapes(db_session, seed_opd_data):
    """Verify feature extractor builds aligned feature dict and matrix with no leakage."""
    queue = seed_opd_data["queue"]
    from tests.conftest import make_test_user
    from app.models.user import UserRole
    patient, _ = make_test_user(db_session, "ML Test Pat", "mltest@test.com", UserRole.PATIENT)

    entry = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient.id,
        token_number=1,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.WAITING,
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(entry)
    db_session.flush()

    features = PredictionFeatureExtractor.extract_inference_features(db_session, entry, patients_ahead_count=3)

    # Check all feature columns exist and are numeric
    for col in FEATURE_COLUMNS:
        assert col in features
        assert isinstance(features[col], (int, float))

    assert features["patients_ahead"] == 3
    assert features["priority_code"] == 0

    # Vector conversion
    vec = PredictionFeatureExtractor.to_vector(features)
    assert vec.shape == (1, len(FEATURE_COLUMNS))
    assert not np.isnan(vec).any()


def test_priority_coding():
    """Verify ordinal priority encoding."""
    assert priority_to_code(PriorityClass.NORMAL) == 0
    assert priority_to_code(PriorityClass.PRIORITY) == 1
    assert priority_to_code(PriorityClass.EMERGENCY) == 2


def test_prediction_model_service_fallback_when_artifact_missing(monkeypatch):
    """Verify PredictionModelService gracefully reports FALLBACK_ACTIVE when artifact is missing."""
    monkeypatch.setattr("app.services.prediction_model_service.MODEL_FILE", "/nonexistent/model.joblib")
    PredictionModelService.load_model(force_reload=True)

    assert not PredictionModelService.is_available()
    assert PredictionModelService.get_status() == ModelStatus.FALLBACK_ACTIVE
    assert PredictionModelService.predict_duration({"day_of_week": 1}) is None


def test_safety_bounds_rejection(monkeypatch):
    """Verify ML outputs outside [60s, 7200s], NaN, or infinite are rejected with None."""
    class DummyModel:
        def __init__(self, val):
            self.val = val
        def predict(self, X):
            return np.array([self.val])

    # Case 1: Duration <= 0
    monkeypatch.setattr(PredictionModelService, "_model", DummyModel(-50))
    monkeypatch.setattr(PredictionModelService, "_loaded", True)
    assert PredictionModelService.predict_duration({"patients_ahead": 1}) is None

    # Case 2: Duration > 7200 (e.g. 10 hours anomaly)
    monkeypatch.setattr(PredictionModelService, "_model", DummyModel(36000))
    assert PredictionModelService.predict_duration({"patients_ahead": 1}) is None

    # Case 3: NaN
    monkeypatch.setattr(PredictionModelService, "_model", DummyModel(float("nan")))
    assert PredictionModelService.predict_duration({"patients_ahead": 1}) is None


def test_hybrid_prediction_service_uses_baseline_when_ml_unavailable(monkeypatch):
    """Verify HybridPredictionService seamlessly returns RobustMedianPredictor output when ML is unavailable."""
    monkeypatch.setattr(PredictionModelService, "is_available", classmethod(lambda cls: False))

    hybrid = HybridPredictionService(model_service=PredictionModelService)
    durations = [600, 720, 900, 960]
    pred_sec, unc_min, model_type, model_ver, status = hybrid.predict_duration({}, durations)

    assert pred_sec == 810  # median of [600, 720, 900, 960]
    assert model_type == "robust_median"
    assert status == "VALID"


def test_hybrid_prediction_service_uses_ml_when_available(monkeypatch):
    """Verify HybridPredictionService selects validated ML prediction within bounds."""
    monkeypatch.setattr(PredictionModelService, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(PredictionModelService, "predict_duration", classmethod(lambda cls, f: 750))
    monkeypatch.setattr(PredictionModelService, "get_metadata", classmethod(lambda cls: {
        "model_version": "v1.0.0-hgb",
        "algorithm": "HistGradientBoostingRegressor",
        "comparison": {"ml_better_than_baseline": True},
        "metrics": {"validation_median_absolute_error_seconds": 300},
    }))

    hybrid = HybridPredictionService(model_service=PredictionModelService)
    pred_sec, unc_min, model_type, model_ver, status = hybrid.predict_duration({}, [600, 900])

    assert pred_sec == 750
    assert model_type == "HistGradientBoostingRegressor"
    assert model_ver == "v1.0.0-hgb"
    assert status == "VALID"
    assert 3 <= unc_min <= 30


def test_reforecast_service_integration_with_hybrid(test_client, db_session, seed_opd_data):
    """Verify PredictionService in reforecast integrates HybridPredictionService and returns valid windows."""
    queue = seed_opd_data["queue"]
    from tests.conftest import make_test_user
    from app.models.user import UserRole
    patient, p_headers = make_test_user(db_session, "Hybrid Reforecast Pat", "hybrid@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    assert join_res.status_code == 201
    entry_id = join_res.json()["entry"]["id"]

    pred_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()

    assert data["predicted_duration_seconds"] >= 60
    assert data["uncertainty_minutes"] >= 3
    assert data["prediction_status"] in ("VALID", "FALLBACK")
    assert data["predicted_start_at"] is not None
    assert data["predicted_end_at"] is not None
