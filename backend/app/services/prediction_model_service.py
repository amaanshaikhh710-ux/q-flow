"""Prediction model service — loads, validates, and manages ML model artifacts."""

import os
import json
import logging
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import numpy as np

from app.services.prediction_features import PredictionFeatureExtractor, FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Model Artifact Locations
ARTIFACT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", "artifacts"))
MODEL_FILE = os.path.join(ARTIFACT_DIR, "duration_model_v1.joblib")
META_FILE = os.path.join(ARTIFACT_DIR, "duration_model_v1_meta.json")

# Safety Bounds for Clinical Consultation Durations (Seconds)
MIN_SAFE_DURATION_SECONDS = 60      # 1 minute minimum
MAX_SAFE_DURATION_SECONDS = 7200    # 2 hours maximum


class ModelStatus(str, Enum):
    ML_AVAILABLE = "ML_AVAILABLE"
    ML_UNAVAILABLE = "ML_UNAVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FALLBACK_ACTIVE = "FALLBACK_ACTIVE"


class PredictionModelService:
    """Service to load and query trained ML duration models."""

    _model: Optional[Any] = None
    _meta: Optional[Dict[str, Any]] = None
    _loaded: bool = False

    @classmethod
    def load_model(cls, force_reload: bool = False) -> bool:
        """Load model artifact and metadata if available on disk."""
        if cls._loaded and not force_reload:
            return cls._model is not None

        cls._model = None
        cls._meta = None
        cls._loaded = True

        if not os.path.exists(MODEL_FILE):
            logger.info("ML duration model not found at %s. Baseline fallback active.", MODEL_FILE)
            return False

        try:
            import joblib
            cls._model = joblib.load(MODEL_FILE)
            if os.path.exists(META_FILE):
                with open(META_FILE, "r", encoding="utf-8") as f:
                    cls._meta = json.load(f)
            logger.info("Loaded ML duration model from %s (Algorithm: %s)", MODEL_FILE, cls._meta.get("algorithm") if cls._meta else "Unknown")
            return True
        except Exception as e:
            logger.warning("Failed to load ML duration model: %s. Using baseline fallback.", e)
            cls._model = None
            cls._meta = None
            return False

    @classmethod
    def is_available(cls) -> bool:
        """Return True if model is loaded and ready for inference."""
        if not cls._loaded:
            cls.load_model()
        return cls._model is not None

    @classmethod
    def get_status(cls) -> ModelStatus:
        """Get model health and readiness status."""
        if cls.is_available():
            return ModelStatus.ML_AVAILABLE
        return ModelStatus.FALLBACK_ACTIVE

    @classmethod
    def get_metadata(cls) -> Optional[Dict[str, Any]]:
        """Return model training metadata and evaluation metrics."""
        if not cls._loaded:
            cls.load_model()
        return cls._meta

    @classmethod
    def predict_duration(cls, features: Dict[str, Any]) -> Optional[int]:
        """Predict expected duration in seconds with strict safety bounds.

        Returns None if model is unavailable, output is invalid, or outside safety bounds.
        """
        if not cls.is_available():
            return None

        try:
            X = PredictionFeatureExtractor.to_vector(features)
            raw_pred = cls._model.predict(X)[0]

            # Reject invalid outputs: NaN, infinite, non-positive, or extreme anomalies
            if np.isnan(raw_pred) or np.isinf(raw_pred):
                logger.warning("ML model produced NaN or Infinite output: %s", raw_pred)
                return None

            duration_sec = int(round(float(raw_pred)))
            if duration_sec < MIN_SAFE_DURATION_SECONDS or duration_sec > MAX_SAFE_DURATION_SECONDS:
                logger.warning("ML prediction %d seconds violates clinical safety bounds [%d, %d]",
                               duration_sec, MIN_SAFE_DURATION_SECONDS, MAX_SAFE_DURATION_SECONDS)
                return None

            return duration_sec
        except Exception as e:
            logger.warning("ML prediction calculation error: %s", e)
            return None
