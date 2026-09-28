"""Pydantic schemas for consultation duration, start time predictions, uncertainty windows, and reforecasting."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class PredictionResponse(BaseModel):
    """Authoritative prediction response representing uncertainty-aware consultation window."""
    id: uuid.UUID
    queue_entry_id: uuid.UUID
    queue_id: uuid.UUID
    predicted_start_at: datetime
    predicted_end_at: datetime
    predicted_duration_seconds: int = Field(..., ge=0, description="Predicted consultation duration in seconds")
    predicted_duration_minutes: int = Field(..., ge=0, description="Rounded duration in minutes")
    uncertainty_margin_seconds: int = Field(..., ge=0, description="Uncertainty window margin in seconds")
    uncertainty_minutes: int = Field(..., ge=0, description="Uncertainty window margin in minutes")
    patients_ahead_count: int = Field(0, ge=0, description="Active patients currently ahead in queue")
    explanation: Optional[str] = Field(None, description="Patient-facing explanation for estimate or change")
    explanation_text: Optional[str] = None
    explanation_json: Dict[str, Any] = {}
    feature_snapshot_json: Dict[str, Any] = {}
    model_type: str
    model_version: str
    prediction_status: str
    trigger_event_id: Optional[uuid.UUID] = None
    is_meaningful_change: bool = False
    shift_minutes: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class PredictionHistoryResponse(BaseModel):
    """Chronological history of prediction snapshots for a queue ticket."""
    queue_entry_id: uuid.UUID
    total_snapshots: int
    history: List[PredictionResponse]


class PredictionQueueSummaryResponse(BaseModel):
    """Current predictions for all active waiting patients in a queue."""
    queue_id: uuid.UUID
    generated_at: datetime
    active_count: int
    predictions: List[PredictionResponse]


class ReforecastTriggerResponse(BaseModel):
    """Response returned when staff explicitly triggers queue reforecasting."""
    success: bool = True
    queue_id: uuid.UUID
    reforecasted_count: int
    meaningful_change_count: int
    message: str
