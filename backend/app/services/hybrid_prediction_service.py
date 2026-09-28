"""Hybrid Prediction Service — combines robust statistical baseline with validated ML predictions."""

import logging
from typing import Dict, Any, List, Tuple, Optional

from app.services.prediction_engine import (
    BaseDurationPredictor,
    RobustMedianPredictor,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
)
from app.services.prediction_model_service import (
    PredictionModelService,
    MIN_SAFE_DURATION_SECONDS,
    MAX_SAFE_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)


class HybridPredictionService(BaseDurationPredictor):
    """Hybrid predictor implementing BaseDurationPredictor.

    Flow:
    1. Always compute robust statistical baseline.
    2. Check if ML model is available and validated.
    3. If ML output is within bounds [60s, 7200s] and model outperformed baseline, select ML.
    4. Derive calibrated uncertainty window margin (3 to 30 minutes).
    5. Fallback seamlessly to baseline if ML fails or is unavailable.
    """

    def __init__(self, model_service: Optional[type[PredictionModelService]] = None):
        self.baseline = RobustMedianPredictor()
        self.model_service = model_service or PredictionModelService

    def predict_duration(
        self,
        features: Dict[str, Any],
        historical_durations: List[int],
    ) -> Tuple[int, int, str, str, str]:
        """Estimate expected duration and uncertainty.

        Returns:
            Tuple[predicted_duration_seconds, uncertainty_minutes, model_type, model_version, prediction_status]
        """
        # Step 1: Compute robust baseline
        base_sec, base_unc, base_type, base_ver, base_status = self.baseline.predict_duration(
            features=features,
            historical_durations=historical_durations,
        )

        # Step 2: Check ML availability
        if not self.model_service.is_available():
            return base_sec, base_unc, base_type, base_ver, base_status

        # Step 3: Run ML inference
        ml_pred_sec = self.model_service.predict_duration(features)

        # Step 4: Safety bounds check and validation policy
        if ml_pred_sec is not None and MIN_SAFE_DURATION_SECONDS <= ml_pred_sec <= MAX_SAFE_DURATION_SECONDS:
            meta = self.model_service.get_metadata() or {}
            model_ver = meta.get("model_version", "ml-v1")
            model_type = meta.get("algorithm", "hist_gradient_boosting")

            # Check if ML was verified better than baseline during training
            ml_better = meta.get("comparison", {}).get("ml_better_than_baseline", True)
            if ml_better:
                # Use calibrated uncertainty from model validation MAD/MAE if available
                val_mad_sec = meta.get("metrics", {}).get("validation_median_absolute_error_seconds", base_unc * 60)
                calibrated_unc_min = max(3, min(30, int(round(val_mad_sec / 60))))

                return ml_pred_sec, calibrated_unc_min, model_type, model_ver, "VALID"

        # Step 5: Fallback to baseline
        return base_sec, base_unc, base_type, base_ver, base_status
