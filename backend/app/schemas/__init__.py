"""Schemas package."""

from app.schemas.common import APIResponse
from app.schemas.health import HealthResponse
from app.schemas.auth import (
    UserRegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
    LogoutResponse,
)

from app.schemas.queue import (
    QueueResponse,
    QueueEntryResponse,
    QueueJoinResponse,
    PriorityUpdateRequest,
    EmergencyInsertRequest,
    DoctorDelayRequest,
    DoctorBreakRequest,
    ConsultationCompleteRequest,
    NoShowRequest,
    TemporaryLeaveRequest,
    RequeueRequest,
    QueueSnapshotResponse,
    AffectedEntriesResponse,
)

from app.schemas.prediction import (
    PredictionResponse,
    PredictionHistoryResponse,
    PredictionQueueSummaryResponse,
    ReforecastTriggerResponse,
)

from app.schemas.travel import (
    TravelOriginRequest,
    TravelEstimateResponse,
    ArrivalPlanResponse,
    ArrivalPlanHistoryResponse,
)

__all__ = [
    "APIResponse",
    "HealthResponse",
    "UserRegisterRequest",
    "LoginRequest",
    "UserResponse",
    "TokenResponse",
    "LogoutResponse",
    "QueueResponse",
    "QueueEntryResponse",
    "QueueJoinResponse",
    "PriorityUpdateRequest",
    "EmergencyInsertRequest",
    "DoctorDelayRequest",
    "DoctorBreakRequest",
    "ConsultationCompleteRequest",
    "NoShowRequest",
    "TemporaryLeaveRequest",
    "RequeueRequest",
    "QueueSnapshotResponse",
    "AffectedEntriesResponse",
    "PredictionResponse",
    "PredictionHistoryResponse",
    "PredictionQueueSummaryResponse",
    "ReforecastTriggerResponse",
    "TravelOriginRequest",
    "TravelEstimateResponse",
    "ArrivalPlanResponse",
    "ArrivalPlanHistoryResponse",
]

