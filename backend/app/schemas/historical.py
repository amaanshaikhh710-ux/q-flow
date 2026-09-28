"""Pydantic schemas for hospital historical reporting, analytics, and exports."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HistoricalAppointmentItem(BaseModel):
    """Schema representing an operational appointment record for historical reporting."""
    id: uuid.UUID
    token_number: int
    token_display: str
    date: datetime = Field(..., description="Timestamp when the appointment was created/joined")
    booking_source: str = Field("ONLINE", description="Source: ONLINE, PHONE, WALK_IN, STAFF")
    doctor_id: uuid.UUID
    doctor_name: str
    department_id: uuid.UUID
    department_name: str
    queue_id: uuid.UUID
    queue_name: str
    patient_name: str
    patient_phone: Optional[str] = None
    arrived_at: Optional[datetime] = None
    consultation_started_at: Optional[datetime] = None
    consultation_completed_at: Optional[datetime] = None
    consultation_duration_seconds: Optional[int] = None
    consultation_duration_minutes: Optional[float] = None
    waiting_time_seconds: Optional[int] = None
    waiting_time_minutes: Optional[float] = None
    status: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HistoricalAppointmentsResponse(BaseModel):
    """Paginated response for historical appointments."""
    items: List[HistoricalAppointmentItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
