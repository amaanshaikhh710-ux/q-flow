"""Prediction Engine — statistical duration predictors, robust outlier handling, and fallback hierarchy."""

import abc
import uuid
import statistics
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.opd_session import OPDSession
from app.models.doctor import Doctor
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass


# Default clinical fallback constants
SAFE_DEFAULT_DURATION_SECONDS = 900  # 15 minutes
SAFE_DEFAULT_UNCERTAINTY_MINUTES = 5
MIN_HISTORICAL_SAMPLE_SIZE = 3
MIN_VALID_DURATION_SECONDS = 60      # 1 minute minimum plausible clinical consult
MAX_VALID_DURATION_SECONDS = 7200    # 2 hours maximum (filter extreme outliers/errors)


class BaseDurationPredictor(abc.ABC):
    """Abstract interface for service duration predictors."""

    @abc.abstractmethod
    def predict_duration(
        self,
        features: Dict[str, Any],
        historical_durations: List[int],
    ) -> Tuple[int, int, str, str, str]:
        """Estimate expected duration in seconds and uncertainty in minutes.

        Returns:
            Tuple[predicted_duration_seconds, uncertainty_minutes, model_type, model_version, prediction_status]
        """
        pass


from enum import Enum
from dataclasses import dataclass


class OutlierClass(str, Enum):
    """Statistical classification for clinical consultation observations."""
    NORMAL = "NORMAL"
    LEGITIMATE_LONG = "LEGITIMATE_LONG"
    EXTREME_ANOMALY = "EXTREME_ANOMALY"
    UNUSUALLY_SHORT = "UNUSUALLY_SHORT"


@dataclass
class OutlierClassificationSummary:
    """Diagnostic breakdown of historical consultation durations."""
    sample_count: int
    normal_count: int
    legitimate_long_count: int
    extreme_anomaly_count: int
    unusually_short_count: int
    median_seconds: int
    mad_seconds: int
    iqr_seconds: int
    robust_estimate_seconds: int
    uncertainty_minutes: int
    method: str = "IQR_HUBER_WEIGHTED"


class OutlierAwareDurationPredictor(BaseDurationPredictor):
    """Layer A: Outlier-aware robust statistical predictor.
    
    Outlier Treatment Methodology:
    1. Clinical consultations follow heavy-tailed distributions. Pure arithmetic mean is easily
       distorted by extreme system clock anomalies (e.g., 300+ minutes from forgotten completion).
       Pure median ignores genuine clinical evidence that complex long consultations do occur.
    2. Statistical Quartile Analysis (IQR):
       - Computes Q1 (25th percentile), Q3 (75th percentile), and IQR = Q3 - Q1.
       - Bounds:
         * Normal Range: [Q1 - 1.5 * IQR, Q3 + 1.5 * IQR]
         * Legitimate Long: (Q3 + 1.5 * IQR, min(Q3 + 3.0 * IQR, 5400s)]
         * Extreme Anomaly: > max(5400s, Q3 + 3.0 * IQR)
         * Unusually Short: < max(60s, Q1 - 1.5 * IQR)
    3. Classification & Weighting (Huber-style loss):
       - NORMAL (weight 1.0): Standard consultation flow.
       - LEGITIMATE_LONG (weight 0.65): Preserved as genuine clinical evidence. Appropriately
         increases the predicted duration so downstream patients are not surprised by long cases.
       - EXTREME_ANOMALY (weight 0.05, Winsorized to upper bound): Down-weighted to prevent system/data
         entry glitches from inflating patient wait estimates by hours.
       - UNUSUALLY_SHORT (weight 0.50): Down-weighted to prevent rapid triage redirects from artificially
         depressing full clinical consult expectations.
    4. Uncertainty Window:
       - Derived honestly from Median Absolute Deviation (MAD) bounded between 3 and 30 minutes.
    """

    def filter_valid_durations(self, durations: List[int], max_seconds: int = MAX_VALID_DURATION_SECONDS) -> List[int]:
        """Filter out non-positive durations and extreme outages exceeding max_seconds."""
        return [
            int(d) for d in durations
            if d is not None and MIN_VALID_DURATION_SECONDS <= d <= max_seconds
        ]

    def analyze_outliers(self, durations: List[int]) -> OutlierClassificationSummary:
        """Analyze sample distribution and classify all observations."""
        valid = sorted(self.filter_valid_durations(durations, max_seconds=28800))
        n = len(valid)

        if n < MIN_HISTORICAL_SAMPLE_SIZE:
            return OutlierClassificationSummary(
                sample_count=n,
                normal_count=0,
                legitimate_long_count=0,
                extreme_anomaly_count=0,
                unusually_short_count=0,
                median_seconds=SAFE_DEFAULT_DURATION_SECONDS,
                mad_seconds=SAFE_DEFAULT_UNCERTAINTY_MINUTES * 60,
                iqr_seconds=0,
                robust_estimate_seconds=SAFE_DEFAULT_DURATION_SECONDS,
                uncertainty_minutes=SAFE_DEFAULT_UNCERTAINTY_MINUTES,
                method="SAFE_FALLBACK",
            )

        med = int(round(statistics.median(valid)))

        # Robust dispersion via Median Absolute Deviation (MAD)
        deviations = [abs(d - med) for d in valid]
        mad = int(round(statistics.median(deviations))) if deviations else 180
        # Normal-consistent scale estimate: sigma = 1.4826 * MAD
        mad_scale = max(180, int(round(1.4826 * mad)))

        # Quartile calculation
        if n >= 4:
            half = n // 2
            q1 = statistics.median(valid[:half])
            q3 = statistics.median(valid[half if n % 2 == 0 else half + 1:])
            iqr = max(120, int(round(q3 - q1)))
        else:
            q1 = valid[0]
            q3 = valid[-1]
            iqr = max(180, int(round(med * 0.3)))

        # Robust normal boundaries combining IQR and MAD dispersion
        lower_normal = max(MIN_VALID_DURATION_SECONDS, min(int(round(q1 - 1.5 * iqr)), med - 2 * mad_scale))
        upper_normal = max(1200, min(int(round(q3 + 1.5 * iqr)), med + max(600, 3 * mad_scale)))
        upper_legitimate = max(upper_normal + 300, min(MAX_VALID_DURATION_SECONDS, max(5400, int(round(q3 + 3.0 * iqr)))))

        normal_count = 0
        legit_long_count = 0
        extreme_count = 0
        short_count = 0

        weighted_sum = 0.0
        weights_sum = 0.0

        for d in valid:
            if d < lower_normal:
                short_count += 1
                w = 0.50
                val = d
            elif d <= upper_normal:
                normal_count += 1
                w = 1.00
                val = d
            elif d <= upper_legitimate:
                legit_long_count += 1
                # Preserved as clinical evidence with high weight (0.65)
                w = 0.65
                val = d
            else:
                extreme_count += 1
                # Extreme system anomaly: heavily down-weighted and Winsorized to upper bound
                w = 0.05
                val = upper_legitimate

            weighted_sum += w * val
            weights_sum += w

        if legit_long_count == 0 and extreme_count == 0 and short_count == 0:
            robust_est = med
        else:
            robust_est = int(round(weighted_sum / weights_sum)) if weights_sum > 0 else med

        # Median Absolute Deviation (MAD) for calibrated clinical uncertainty
        deviations = [abs(d - med) for d in valid]
        mad = int(round(statistics.median(deviations))) if deviations else 180

        # Uncertainty expansion if legitimate long cases are present
        variability_penalty = 120 if legit_long_count > 0 else 0
        uncertainty_min = max(3, min(30, int(round((mad + variability_penalty) / 60))))

        return OutlierClassificationSummary(
            sample_count=n,
            normal_count=normal_count,
            legitimate_long_count=legit_long_count,
            extreme_anomaly_count=extreme_count,
            unusually_short_count=short_count,
            median_seconds=med,
            mad_seconds=mad,
            iqr_seconds=iqr,
            robust_estimate_seconds=robust_est,
            uncertainty_minutes=uncertainty_min,
            method="IQR_HUBER_WEIGHTED",
        )

    def predict_duration(
        self,
        features: Dict[str, Any],
        historical_durations: List[int],
    ) -> Tuple[int, int, str, str, str]:
        """Calculate outlier-aware robust consultation duration and honest uncertainty."""
        summary = self.analyze_outliers(historical_durations)

        if summary.sample_count < MIN_HISTORICAL_SAMPLE_SIZE:
            return (
                SAFE_DEFAULT_DURATION_SECONDS,
                SAFE_DEFAULT_UNCERTAINTY_MINUTES,
                "robust_median",
                "baseline-v1",
                "FALLBACK",
            )

        # Store classification diagnostics in features for explainability and snapshots
        features["outlier_analysis"] = {
            "sample_count": summary.sample_count,
            "normal_count": summary.normal_count,
            "legitimate_long_count": summary.legitimate_long_count,
            "extreme_anomaly_count": summary.extreme_anomaly_count,
            "unusually_short_count": summary.unusually_short_count,
            "median_seconds": summary.median_seconds,
            "mad_seconds": summary.mad_seconds,
            "iqr_seconds": summary.iqr_seconds,
            "outlier_treatment": summary.method,
        }

        return (
            summary.robust_estimate_seconds,
            summary.uncertainty_minutes,
            "robust_median",
            "baseline-v1",
            "VALID",
        )


# Backward-compatible alias
RobustMedianPredictor = OutlierAwareDurationPredictor


class SklearnDurationPredictor(BaseDurationPredictor):
    """Layer B: Extensible tabular ML predictor (gracefully falls back to baseline)."""

    def __init__(self, model_artifact: Optional[Any] = None):
        self.model_artifact = model_artifact
        self.baseline_fallback = RobustMedianPredictor()

    def predict_duration(
        self,
        features: Dict[str, Any],
        historical_durations: List[int],
    ) -> Tuple[int, int, str, str, str]:
        """Predict using ML model if available and trained; fallback to baseline otherwise."""
        if self.model_artifact is None:
            # Automatic graceful degradation
            pred_sec, unc_min, _, _, _ = self.baseline_fallback.predict_duration(features, historical_durations)
            return pred_sec, unc_min, "sklearn_tabular", "ml-stub-v1", "FALLBACK"

        # When trained model exists in future phases:
        # X = extract_features(features)
        # return int(self.model_artifact.predict(X)[0]), unc_min, "sklearn_tabular", "ml-v1", "VALID"
        return self.baseline_fallback.predict_duration(features, historical_durations)


class PredictionFeatureBuilder:
    """Service to extract structured features and fetch historical data across the fallback hierarchy."""

    @staticmethod
    def get_historical_durations(
        db: Session,
        doctor_id: Optional[uuid.UUID],
        department_id: Optional[uuid.UUID],
    ) -> Tuple[List[int], str]:
        """Fetch completed consultation durations following the 5-tier fallback hierarchy:
        1. Doctor + Department recent (last 30 days)
        2. Doctor overall historical
        3. Department overall historical
        4. Global clinic historical
        5. Safe default
        """
        now = datetime.now(timezone.utc)
        recent_threshold = now - timedelta(days=30)

        # Tier 1: Doctor + Department recent
        if doctor_id and department_id:
            tier1_rows = (
                db.query(Consultation.duration_seconds)
                .join(Doctor, Consultation.doctor_id == Doctor.id)
                .filter(
                    Consultation.doctor_id == doctor_id,
                    Doctor.department_id == department_id,
                    Consultation.completed_at >= recent_threshold,
                    Consultation.duration_seconds.isnot(None),
                    Consultation.duration_seconds >= MIN_VALID_DURATION_SECONDS,
                )
                .all()
            )
            tier1 = [r[0] for r in tier1_rows if r[0] is not None]
            if len(tier1) >= MIN_HISTORICAL_SAMPLE_SIZE:
                return tier1, "doctor_department_recent"

        # Tier 2: Doctor overall historical
        if doctor_id:
            tier2_rows = (
                db.query(Consultation.duration_seconds)
                .filter(
                    Consultation.doctor_id == doctor_id,
                    Consultation.duration_seconds.isnot(None),
                    Consultation.duration_seconds >= MIN_VALID_DURATION_SECONDS,
                )
                .all()
            )
            tier2 = [r[0] for r in tier2_rows if r[0] is not None]
            if len(tier2) >= MIN_HISTORICAL_SAMPLE_SIZE:
                return tier2, "doctor_historical"

        # Tier 3: Department overall historical
        if department_id:
            tier3_rows = (
                db.query(Consultation.duration_seconds)
                .join(Doctor, Consultation.doctor_id == Doctor.id)
                .filter(
                    Doctor.department_id == department_id,
                    Consultation.duration_seconds.isnot(None),
                    Consultation.duration_seconds >= MIN_VALID_DURATION_SECONDS,
                )
                .all()
            )
            tier3 = [r[0] for r in tier3_rows if r[0] is not None]
            if len(tier3) >= MIN_HISTORICAL_SAMPLE_SIZE:
                return tier3, "department_historical"

        # Tier 4: Global clinic historical
        tier4_rows = (
            db.query(Consultation.duration_seconds)
            .filter(
                Consultation.duration_seconds.isnot(None),
                Consultation.duration_seconds >= MIN_VALID_DURATION_SECONDS,
            )
            .limit(200)
            .all()
        )
        tier4 = [r[0] for r in tier4_rows if r[0] is not None]
        if len(tier4) >= MIN_HISTORICAL_SAMPLE_SIZE:
            return tier4, "global_historical"

        # Tier 5: Safe default
        return [], "safe_default"

    @staticmethod
    def build_entry_features(
        db: Session,
        entry: QueueEntry,
        patients_ahead: int,
    ) -> Dict[str, Any]:
        """Construct deterministic feature vector for an entry."""
        queue = entry.queue
        opd_session = queue.opd_session if queue else None
        now = datetime.now(timezone.utc)

        return {
            "queue_entry_id": str(entry.id),
            "queue_id": str(entry.queue_id),
            "doctor_id": str(opd_session.doctor_id) if opd_session else None,
            "department_id": str(opd_session.department_id) if opd_session else None,
            "priority_class": entry.priority_class.value,
            "patients_ahead": patients_ahead,
            "day_of_week": now.weekday(),
            "hour_of_day": now.hour,
            "minute_of_hour": now.minute,
        }
