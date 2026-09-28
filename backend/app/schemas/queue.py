"""Pydantic schemas for Queue operations, tokens, entries, and snapshots."""

import uuid
from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.queue import QueueStatus
from app.models.queue_entry import PriorityClass, QueueEntryStatus


class QueueResponse(BaseModel):
    """Authoritative representation of a queue."""
    id: uuid.UUID
    opd_session_id: uuid.UUID
    name: str
    queue_date: date
    status: QueueStatus
    current_position: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueEntryResponse(BaseModel):
    """Authoritative queue ticket / entry representation."""
    id: uuid.UUID
    queue_id: uuid.UUID
    patient_user_id: uuid.UUID
    token_number: int
    token_display: str = Field(..., description="Server-formatted display token, e.g. Q001")
    priority_class: PriorityClass
    status: QueueEntryStatus
    booking_source: str = "ONLINE"
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    notes: Optional[str] = None
    position: Optional[int] = Field(None, description="Calculated 1-indexed waiting position; 0 if called/serving; null if inactive")
    appointment_date: Optional[date] = None
    schedule_id: Optional[uuid.UUID] = None
    appointment_time: Optional[time] = None
    joined_at: datetime
    arrived_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    temporary_left_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    no_show_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def validate_canonical_calendar_year(v: Optional[date]) -> Optional[date]:
    if v is not None:
        if v.year < 2000 or v.year > 2100:
            raise ValueError(f"Invalid calendar date '{v}'. Year must be between 2000 and 2100.")
    return v


class CreateQueueRequest(BaseModel):
    """Staff payload to create an OPD session and doctor queue for a specific date and time window."""
    doctor_id: uuid.UUID = Field(..., description="Target doctor ID")
    queue_date: date = Field(..., description="Target operational date for the queue")
    start_time: time = Field(..., description="OPD session start time (e.g. 09:00:00)")
    end_time: time = Field(..., description="OPD session end time (e.g. 13:00:00)")

    @field_validator("queue_date", mode="after")
    @classmethod
    def validate_queue_date(cls, v: date) -> date:
        return validate_canonical_calendar_year(v)


class QueueJoinRequest(BaseModel):
    """Patient payload to join a queue / book an appointment."""
    appointment_date: Optional[date] = Field(None, description="Target appointment date (defaults to today)")
    appointment_time: Optional[time] = Field(None, description="Optional target time window or slot")

    @field_validator("appointment_date", mode="after")
    @classmethod
    def validate_appointment_date(cls, v: Optional[date]) -> Optional[date]:
        return validate_canonical_calendar_year(v)


class StaffBookAppointmentRequest(BaseModel):
    """Staff payload to create a walk-in, phone, or in-person appointment for a patient."""
    patient_name: str = Field(..., min_length=1, max_length=150, description="Full name of patient")
    patient_phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Patient contact phone")
    booking_source: str = Field("STAFF", description="STAFF, WALK_IN, or PHONE")
    priority_class: Optional[PriorityClass] = Field(PriorityClass.NORMAL, description="Initial triage priority")
    appointment_date: Optional[date] = Field(None, description="Target appointment date (defaults to today for walk-in)")
    appointment_time: Optional[time] = Field(None, description="Optional target time window or slot")
    notes: Optional[str] = Field(None, max_length=500, description="Clinical or check-in notes")

    @field_validator("appointment_date", mode="after")
    @classmethod
    def validate_appointment_date(cls, v: Optional[date]) -> Optional[date]:
        return validate_canonical_calendar_year(v)

    @field_validator("priority_class", mode="before")
    @classmethod
    def normalize_priority(cls, v):
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("normal", "priority", "emergency"):
                return PriorityClass(v_lower)
        return v


class PatientAppointmentItem(BaseModel):
    """Rich appointment representation for patient dashboard."""
    id: uuid.UUID
    queue_id: uuid.UUID
    token_number: int
    token_display: str
    status: QueueEntryStatus
    priority_class: PriorityClass
    booking_source: str = "ONLINE"
    notes: Optional[str] = None
    joined_at: datetime
    arrived_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    position: Optional[int] = None
    appointment_date: Optional[date] = None
    schedule_id: Optional[uuid.UUID] = None
    appointment_time: Optional[time] = None
    
    # Healthcare Hierarchy
    hospital_id: uuid.UUID
    hospital_name: str
    hospital_address: Optional[str] = None
    hospital_latitude: Optional[float] = None
    hospital_longitude: Optional[float] = None
    department_id: uuid.UUID
    department_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    
    # Timing & Travel
    estimated_wait_minutes: Optional[int] = None
    estimated_start_time: Optional[datetime] = None
    latest_departure_time: Optional[datetime] = None
    travel_duration_minutes: Optional[int] = None
    travel_uncertainty_minutes: Optional[int] = None
    travel_mode: str = "DRIVE"
    travel_status: str = "UNAVAILABLE"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientAppointmentsResponse(BaseModel):
    """Response containing appointments for the logged-in patient."""
    today: List[PatientAppointmentItem] = []
    upcoming: List[PatientAppointmentItem] = []
    past: List[PatientAppointmentItem] = []
    total: int = 0


class QueueJoinResponse(BaseModel):
    """Response returned when a patient successfully joins a queue."""
    entry: QueueEntryResponse
    message: str = "Successfully joined queue"


class PriorityUpdateRequest(BaseModel):
    """Staff payload to change an entry's priority rank."""
    priority_class: PriorityClass
    reason: Optional[str] = Field(None, max_length=255)


class EmergencyInsertRequest(BaseModel):
    """Staff payload to insert an emergency patient into the queue."""
    patient_user_id: uuid.UUID
    reason: Optional[str] = Field(None, max_length=255)


class DoctorDelayRequest(BaseModel):
    """Staff payload to record a doctor delay event."""
    delay_minutes: int = Field(..., gt=0, le=480, description="Estimated delay in minutes")
    reason: Optional[str] = Field(None, max_length=255)


class DoctorBreakRequest(BaseModel):
    """Staff payload to record doctor break start."""
    duration_minutes: int = Field(..., gt=0, le=240, description="Estimated break duration in minutes")
    reason: Optional[str] = Field(None, max_length=255)


class ConsultationCompleteRequest(BaseModel):
    """Staff payload to complete a consultation."""
    interruption_notes: Optional[str] = Field(None, max_length=500)


class NoShowRequest(BaseModel):
    """Staff payload to record patient no-show."""
    reason: Optional[str] = Field(None, max_length=255)


class TemporaryLeaveRequest(BaseModel):
    """Payload to record patient temporary leave."""
    reason: Optional[str] = Field(None, max_length=255)


class RequeueRequest(BaseModel):
    """Staff payload to requeue a RETURNED patient into WAITING state."""
    priority_class: Optional[PriorityClass] = None
    reason: Optional[str] = Field(None, max_length=255)


class QueueSnapshotResponse(BaseModel):
    """Authoritative snapshot of the current queue state."""
    queue_id: uuid.UUID
    queue_name: str
    queue_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    hospital_id: Optional[uuid.UUID] = None
    hospital_name: Optional[str] = None
    status: QueueStatus
    opd_session_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    doctor_name: Optional[str] = None
    department_name: Optional[str] = None
    currently_serving: Optional[QueueEntryResponse] = None
    currently_called: Optional[QueueEntryResponse] = None
    next_patient: Optional[QueueEntryResponse] = None
    total_waiting: int
    total_booked: int = 0
    total_active: int = 0
    total_in_consultation: int
    total_completed: int
    total_no_show: int
    waiting_entries: List[QueueEntryResponse] = []
    booked_entries: List[QueueEntryResponse] = []
    avg_consultation_duration_seconds: Optional[int] = None
    avg_waiting_time_seconds: Optional[int] = None
    current_consultation_elapsed_seconds: Optional[int] = None
    delay_impact_minutes: Optional[int] = None
    estimated_remaining_queue_time_minutes: Optional[int] = None


class AffectedEntriesResponse(BaseModel):
    """List of downstream affected queue entries following a mutation."""
    affected_count: int
    affected_entry_ids: List[uuid.UUID]
    affected_entries: List[QueueEntryResponse]
    reason: str
