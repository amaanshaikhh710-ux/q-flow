"""WebSocket message schemas and typed event definitions."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class WebSocketEventType(str, Enum):
    QUEUE_CONNECTED = "QUEUE_CONNECTED"
    QUEUE_SNAPSHOT = "QUEUE_SNAPSHOT"
    QUEUE_REFORECAST = "QUEUE_REFORECAST"
    QUEUE_STATUS_CHANGED = "QUEUE_STATUS_CHANGED"
    CONSULTATION_STARTED = "CONSULTATION_STARTED"
    CONSULTATION_COMPLETED = "CONSULTATION_COMPLETED"
    ARRIVAL_PLAN_UPDATED = "ARRIVAL_PLAN_UPDATED"
    NOTIFICATION_CREATED = "NOTIFICATION_CREATED"
    ERROR = "ERROR"


class PredictionSummaryPayload(BaseModel):
    predicted_start_at: datetime
    predicted_end_at: datetime
    uncertainty_seconds: int = Field(..., ge=0)
    patients_ahead: int = Field(..., ge=0)
    predicted_duration_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ArrivalPlanSummaryPayload(BaseModel):
    arrival_start_at: Optional[datetime] = None
    arrival_end_at: Optional[datetime] = None
    departure_start_at: Optional[datetime] = None
    departure_end_at: Optional[datetime] = None
    travel_status: str

    model_config = ConfigDict(from_attributes=True)


class ExplanationPayload(BaseModel):
    reason_code: Optional[str] = None
    message: str


class WebSocketMessage(BaseModel):
    type: str
    version: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_id: Optional[uuid.UUID] = None
    queue_id: uuid.UUID
    prediction: Optional[PredictionSummaryPayload] = None
    arrival_plan: Optional[ArrivalPlanSummaryPayload] = None
    explanation: Optional[ExplanationPayload] = None
    payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class PatientQueueSnapshot(BaseModel):
    queue_id: uuid.UUID
    entry_id: uuid.UUID
    queue_status: str
    token_display: str
    patient_status: str
    position: Optional[int] = None
    patients_ahead: int = 0
    prediction: Optional[PredictionSummaryPayload] = None
    arrival_plan: Optional[ArrivalPlanSummaryPayload] = None
    explanation: Optional[str] = None
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
