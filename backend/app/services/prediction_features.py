"""Feature engineering pipeline for Q-FLOW ML queue prediction.

Guarantees:
1. Identical feature representations between training and live inference.
2. Strict data leakage prevention (zero future knowledge used).
3. Zero patient PII (strictly operational queue parameters).
4. Safe defaults for cold-start cases.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.models.queue_entry import QueueEntry, PriorityClass, QueueEntryStatus
from app.models.consultation import Consultation
from app.models.opd_session import OPDSession
from app.services.prediction_engine import (
    SAFE_DEFAULT_DURATION_SECONDS,
    MIN_HISTORICAL_SAMPLE_SIZE,
    PredictionFeatureBuilder as BaselineFeatureBuilder,
)


FEATURE_COLUMNS: List[str] = [
    "day_of_week",
    "hour_of_day",
    "minute_of_hour",
    "priority_code",
    "patients_ahead",
    "rolling_recent_duration_median",
    "historical_doctor_duration_median",
    "historical_dept_duration_median",
    "session_elapsed_minutes",
    "completed_in_session_count",
    "has_emergency_ahead",
]


def priority_to_code(priority: Any) -> int:
    """Encode priority class to ordinal code."""
    if priority == PriorityClass.EMERGENCY or priority == "EMERGENCY":
        return 2
    if priority == PriorityClass.PRIORITY or priority == "PRIORITY":
        return 1
    return 0


class PredictionFeatureExtractor:
    """Extracts and normalizes features for duration prediction."""

    @staticmethod
    def extract_inference_features(
        db: Session,
        entry: QueueEntry,
        patients_ahead_count: int = 0,
        reference_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Extract features for a live queue entry at inference time."""
        now = reference_time or datetime.now(timezone.utc)
        queue = entry.queue
        opd_session = queue.opd_session if queue else None

        doctor_id = opd_session.doctor_id if opd_session else None
        dept_id = opd_session.department_id if opd_session else None

        # 1. Doctor & Dept Historical Medians
        doc_history, _ = BaselineFeatureBuilder.get_historical_durations(db, doctor_id, None)
        dept_history, _ = BaselineFeatureBuilder.get_historical_durations(db, None, dept_id)

        doc_median = float(np.median(doc_history)) if len(doc_history) >= MIN_HISTORICAL_SAMPLE_SIZE else float(SAFE_DEFAULT_DURATION_SECONDS)
        dept_median = float(np.median(dept_history)) if len(dept_history) >= MIN_HISTORICAL_SAMPLE_SIZE else float(SAFE_DEFAULT_DURATION_SECONDS)

        # 2. Active Session Progress
        session_elapsed_min = 0.0
        completed_in_session = 0
        recent_durations: List[int] = []

        if opd_session:
            if opd_session.starts_at:
                s_at = opd_session.starts_at
                if s_at.tzinfo is None:
                    s_at = s_at.replace(tzinfo=timezone.utc)
                n_at = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
                session_elapsed_min = max(0.0, (n_at - s_at).total_seconds() / 60.0)

            # Consultations completed in this queue/session prior to now (no leakage)
            session_consults = (
                db.query(Consultation.duration_seconds)
                .join(QueueEntry, Consultation.queue_entry_id == QueueEntry.id)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    Consultation.completed_at.isnot(None),
                    Consultation.completed_at <= now,
                    Consultation.duration_seconds.isnot(None),
                    Consultation.duration_seconds > 0,
                )
                .order_by(Consultation.completed_at.desc())
                .limit(5)
                .all()
            )
            completed_in_session = (
                db.query(Consultation)
                .join(QueueEntry, Consultation.queue_entry_id == QueueEntry.id)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    Consultation.completed_at.isnot(None),
                    Consultation.completed_at <= now,
                )
                .count()
            )
            recent_durations = [r[0] for r in session_consults if r[0] is not None]

        rolling_recent_median = float(np.median(recent_durations)) if len(recent_durations) >= 1 else doc_median

        # 3. Emergency presence in waiting entries ahead
        has_emergency = 0
        if queue:
            emergency_count = (
                db.query(QueueEntry)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    QueueEntry.status == QueueEntryStatus.WAITING,
                    QueueEntry.priority_class == PriorityClass.EMERGENCY,
                    QueueEntry.joined_at < entry.joined_at,
                )
                .count()
            )
            has_emergency = 1 if emergency_count > 0 else 0

        features = {
            "day_of_week": now.weekday(),
            "hour_of_day": now.hour,
            "minute_of_hour": now.minute,
            "priority_code": priority_to_code(entry.priority_class),
            "patients_ahead": max(0, patients_ahead_count),
            "rolling_recent_duration_median": round(rolling_recent_median, 1),
            "historical_doctor_duration_median": round(doc_median, 1),
            "historical_dept_duration_median": round(dept_median, 1),
            "session_elapsed_minutes": round(session_elapsed_min, 1),
            "completed_in_session_count": completed_in_session,
            "has_emergency_ahead": has_emergency,
        }
        return features

    @staticmethod
    def to_vector(features: Dict[str, Any]) -> np.ndarray:
        """Convert feature dictionary into 2D numpy array aligned with FEATURE_COLUMNS."""
        row = [float(features.get(col, 0.0)) for col in FEATURE_COLUMNS]
        return np.array([row], dtype=np.float32)

    @staticmethod
    def to_matrix(features_list: List[Dict[str, Any]]) -> np.ndarray:
        """Convert list of feature dictionaries into 2D numpy array aligned with FEATURE_COLUMNS."""
        rows = [[float(f.get(col, 0.0)) for col in FEATURE_COLUMNS] for f in features_list]
        return np.array(rows, dtype=np.float32)
