"""Prediction and dynamic reforecast API endpoints."""

import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.api.deps import get_current_user, require_staff_or_admin
from app.models.user import User, UserRole
from app.models.queue import Queue
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.prediction_snapshot import PredictionSnapshot
from app.schemas.prediction import (
    PredictionResponse,
    PredictionHistoryResponse,
    PredictionQueueSummaryResponse,
    ReforecastTriggerResponse,
)
from app.services.reforecast_service import PredictionService
from app.services.queue_engine import QueueEngineService

router = APIRouter()
prediction_service = PredictionService()


def serialize_prediction_response(snap: PredictionSnapshot) -> PredictionResponse:
    """Helper to convert model into response schema with duration minutes and honest uncertainty window."""
    return PredictionResponse(
        id=snap.id,
        queue_entry_id=snap.queue_entry_id,
        queue_id=snap.queue_id,
        predicted_start_at=snap.predicted_start_at,
        predicted_end_at=snap.predicted_end_at,
        predicted_duration_seconds=snap.predicted_duration_seconds,
        predicted_duration_minutes=int(round(snap.predicted_duration_seconds / 60)),
        uncertainty_margin_seconds=snap.uncertainty_margin_seconds,
        uncertainty_minutes=snap.uncertainty_minutes,
        patients_ahead_count=snap.patients_ahead_count,
        explanation=snap.explanation,
        model_type=snap.model_type,
        model_version=snap.model_version,
        prediction_status=snap.prediction_status,
        explanation_text=snap.explanation_text,
        explanation_json=snap.explanation_json,
        feature_snapshot_json=snap.feature_snapshot_json,
        trigger_event_id=snap.trigger_event_id,
        is_meaningful_change=snap.is_meaningful_change,
        shift_minutes=snap.shift_minutes,
        created_at=snap.created_at,
    )



@router.get("/queue-entries/{entry_id}/prediction", response_model=PredictionResponse)
def get_entry_prediction(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionResponse:
    """Get the latest uncertainty-aware prediction window for a queue entry.

    Patients can only view their own ticket; Staff/Admin can view any.
    """
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    # RBAC: Patient privacy
    if current_user.role == UserRole.PATIENT and entry.patient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot view predictions for other patients' tickets",
        )

    # Fetch latest prediction snapshot
    latest_snap = (
        db.query(PredictionSnapshot)
        .filter(PredictionSnapshot.queue_entry_id == entry.id)
        .order_by(desc(PredictionSnapshot.created_at))
        .first()
    )

    # If no snapshot exists yet, generate initial prediction on the fly
    if not latest_snap:
        latest_snap = prediction_service.generate_initial_prediction(db, entry.id)

    if not latest_snap:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction is currently unavailable for this queue entry",
        )

    return serialize_prediction_response(latest_snap)


@router.get("/queue-entries/{entry_id}/prediction/history", response_model=PredictionHistoryResponse)
def get_entry_prediction_history(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionHistoryResponse:
    """Get chronological prediction history showing shifts and explanations across reforecasts."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    if current_user.role == UserRole.PATIENT and entry.patient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot view predictions for other patients' tickets",
        )

    snapshots = (
        db.query(PredictionSnapshot)
        .filter(PredictionSnapshot.queue_entry_id == entry.id)
        .order_by(PredictionSnapshot.created_at.asc())
        .all()
    )

    return PredictionHistoryResponse(
        queue_entry_id=entry.id,
        total_snapshots=len(snapshots),
        history=[serialize_prediction_response(s) for s in snapshots],
    )


@router.get("/queues/{queue_id}/predictions", response_model=PredictionQueueSummaryResponse)
def get_queue_predictions(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> PredictionQueueSummaryResponse:
    """Staff/Admin operation: Get latest predictions for all active waiting patients in a queue."""
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue with ID {queue_id} does not exist",
        )

    ordered_waiting = QueueEngineService.get_ordered_waiting_entries(db, queue_id)
    predictions: List[PredictionResponse] = []

    for entry in ordered_waiting:
        snap = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(desc(PredictionSnapshot.created_at))
            .first()
        )
        if not snap:
            snap = prediction_service.generate_initial_prediction(db, entry.id)

        if snap:
            predictions.append(serialize_prediction_response(snap))

    return PredictionQueueSummaryResponse(
        queue_id=queue.id,
        generated_at=datetime.now(timezone.utc),
        active_count=len(predictions),
        predictions=predictions,
    )


@router.post("/queues/{queue_id}/reforecast", response_model=ReforecastTriggerResponse)
def trigger_queue_reforecast(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> ReforecastTriggerResponse:
    """Staff/Admin operation: Force a recalculation of predictions for all active waiting entries."""
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue with ID {queue_id} does not exist",
        )

    ordered_waiting = QueueEngineService.get_ordered_waiting_entries(db, queue_id)
    reforecasted_count = 0
    meaningful_count = 0

    for entry in ordered_waiting:
        calc = prediction_service.calculate_entry_prediction(db, entry)
        prev = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(desc(PredictionSnapshot.created_at))
            .first()
        )
        if prev:
            p_curr = calc["predicted_start_at"]
            p_prev = prev.predicted_start_at
            if p_curr.tzinfo is not None and p_prev.tzinfo is None:
                p_prev = p_prev.replace(tzinfo=timezone.utc)
            elif p_curr.tzinfo is None and p_prev.tzinfo is not None:
                p_curr = p_curr.replace(tzinfo=timezone.utc)
            shift_secs = (p_curr - p_prev).total_seconds()
            shift_mins = int(round(shift_secs / 60))
        else:
            shift_mins = 0

        is_meaningful = abs(shift_mins) >= 10
        if is_meaningful:
            meaningful_count += 1

        snap = PredictionSnapshot(
            queue_entry_id=entry.id,
            queue_id=queue_id,
            predicted_start_at=calc["predicted_start_at"],
            predicted_end_at=calc["predicted_end_at"],
            predicted_duration_seconds=calc["predicted_duration_seconds"],
            uncertainty_minutes=calc["uncertainty_minutes"],
            model_type=calc["model_type"],
            model_version=calc["model_version"],
            prediction_status=calc["prediction_status"],
            explanation_text="Manual reforecast initiated by operational staff.",
            explanation_json={"trigger": "STAFF_MANUAL_REFORECAST", "shift_minutes": shift_mins},
            feature_snapshot_json=calc["features"],
            is_meaningful_change=is_meaningful,
            shift_minutes=shift_mins,
        )
        db.add(snap)
        reforecasted_count += 1

    db.commit()

    return ReforecastTriggerResponse(
        success=True,
        queue_id=queue.id,
        reforecasted_count=reforecasted_count,
        meaningful_change_count=meaningful_count,
        message=f"Successfully reforecasted {reforecasted_count} active entries ({meaningful_count} meaningful changes)",
    )


@router.get("/predictions/model-status", summary="ML Model Health & Diagnostics")
def get_prediction_model_status():
    """Returns the operational status and validation metrics of the ML duration predictor."""
    from app.services.prediction_model_service import PredictionModelService
    status = PredictionModelService.get_status()
    meta = PredictionModelService.get_metadata()
    return {
        "status": status.value,
        "is_available": PredictionModelService.is_available(),
        "model_version": meta.get("model_version") if meta else None,
        "algorithm": meta.get("algorithm") if meta else "RobustMedianPredictor (Baseline)",
        "dataset_label": meta.get("dataset_label") if meta else None,
        "is_synthetic_training_data": meta.get("is_synthetic_training_data") if meta else None,
        "training_samples": meta.get("training_samples") if meta else 0,
        "validation_samples": meta.get("validation_samples") if meta else 0,
        "metrics": meta.get("metrics") if meta else None,
        "comparison": meta.get("comparison") if meta else None,
    }
