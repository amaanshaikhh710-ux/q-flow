"""Service to assemble patient-safe queue snapshots for initial connect and reconnect."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.services.queue_engine import QueueEngineService, format_token
from app.websocket.schemas import (
    PatientQueueSnapshot,
    PredictionSummaryPayload,
    ArrivalPlanSummaryPayload,
)


class WebSocketSnapshotService:
    """Generates patient-safe snapshots from authoritative state without leaking PII or coordinates."""

    @staticmethod
    def build_patient_snapshot(db: Session, entry: QueueEntry) -> Dict[str, Any]:
        """Assemble current patient-safe operational snapshot for WebSocket dispatch."""
        now = datetime.now(timezone.utc)
        queue = entry.queue

        # 1. Authoritative position & patients ahead
        position = QueueEngineService.get_entry_position(db, entry)
        if position is not None and position > 1:
            patients_ahead = position - 1
        elif position == 1:
            patients_ahead = 0
        else:
            patients_ahead = 0

        # 2. Latest prediction snapshot
        latest_pred = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(desc(PredictionSnapshot.created_at))
            .first()
        )

        pred_payload: Optional[Dict[str, Any]] = None
        explanation_text: Optional[str] = None

        if latest_pred:
            pred_payload = {
                "predicted_start_at": latest_pred.predicted_start_at.isoformat(),
                "predicted_end_at": latest_pred.predicted_end_at.isoformat(),
                "uncertainty_seconds": (latest_pred.uncertainty_minutes or 0) * 60,
                "patients_ahead": patients_ahead,
                "predicted_duration_minutes": int(round(latest_pred.predicted_duration_seconds / 60)) if latest_pred.predicted_duration_seconds else None,
            }
            explanation_text = latest_pred.explanation_text

        # 3. Latest arrival plan
        latest_plan = (
            db.query(ArrivalPlan)
            .filter(ArrivalPlan.queue_entry_id == entry.id)
            .order_by(desc(ArrivalPlan.created_at))
            .first()
        )

        plan_payload: Optional[Dict[str, Any]] = None
        if latest_plan:
            plan_payload = {
                "arrival_start_at": latest_plan.arrival_start_at.isoformat() if latest_plan.arrival_start_at else None,
                "arrival_end_at": latest_plan.arrival_end_at.isoformat() if latest_plan.arrival_end_at else None,
                "departure_start_at": latest_plan.departure_start_at.isoformat() if latest_plan.departure_start_at else None,
                "departure_end_at": latest_plan.departure_end_at.isoformat() if latest_plan.departure_end_at else None,
                "travel_status": latest_plan.travel_status,
            }
            if not explanation_text:
                explanation_text = latest_plan.explanation

        # 4. Construct patient-safe dictionary (Strictly NO coordinates, NO PII of others)
        snapshot = {
            "type": "QUEUE_SNAPSHOT",
            "version": 1,
            "timestamp": now.isoformat(),
            "queue_id": str(entry.queue_id),
            "entry_id": str(entry.id),
            "queue_status": queue.status.value if queue else "ACTIVE",
            "token_display": format_token(entry.token_number),
            "patient_status": entry.status.value,
            "position": position,
            "patients_ahead": patients_ahead,
            "prediction": pred_payload,
            "arrival_plan": plan_payload,
            "explanation": explanation_text,
            "last_updated_at": now.isoformat(),
        }
        return snapshot
