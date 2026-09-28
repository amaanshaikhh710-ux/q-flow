"""Pydantic schemas for Doctor Daily/Weekly Scheduling."""

import uuid
from datetime import date, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def format_time_12h(t: time) -> str:
    """Format time object to 12-hour string (e.g., 09:00 AM)."""
    return t.strftime("%I:%M %p")


def validate_canonical_calendar_year(v: Optional[date]) -> Optional[date]:
    if v is not None:
        if v.year < 2000 or v.year > 2100:
            raise ValueError(f"Invalid calendar date '{v}'. Year must be between 2000 and 2100.")
    return v


class DoctorScheduleCreateRequest(BaseModel):
    doctor_id: uuid.UUID
    schedule_date: date
    start_time: time = Field(default=time(9, 0), description="Shift start time, e.g. 09:00")
    end_time: time = Field(default=time(13, 0), description="Shift end time, e.g. 13:00")
    status: str = Field(default="AVAILABLE", description="AVAILABLE or UNAVAILABLE")

    @field_validator("schedule_date", mode="after")
    @classmethod
    def validate_schedule_date(cls, v: date) -> date:
        return validate_canonical_calendar_year(v)


class DoctorScheduleUpdateRequest(BaseModel):
    start_time: Optional[time] = Field(None, description="Updated start time")
    end_time: Optional[time] = Field(None, description="Updated end time")
    status: Optional[str] = Field(None, description="AVAILABLE or UNAVAILABLE/OFF")


class DoctorScheduleBatchItem(BaseModel):
    schedule_date: date
    start_time: time = Field(default=time(9, 0))
    end_time: time = Field(default=time(13, 0))
    status: str = Field(default="AVAILABLE")

    @field_validator("schedule_date", mode="after")
    @classmethod
    def validate_batch_schedule_date(cls, v: date) -> date:
        return validate_canonical_calendar_year(v)


class DoctorScheduleBatchRequest(BaseModel):
    doctor_id: uuid.UUID
    schedules: List[DoctorScheduleBatchItem]


class DoctorScheduleResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    hospital_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    department_id: uuid.UUID
    department_name: str
    schedule_date: date
    start_time: str
    end_time: str
    start_time_formatted: str
    end_time_formatted: str
    status: str
    appointments_count: int = 0
    queue_id: Optional[uuid.UUID] = None
    queue_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AvailableDoctorItem(BaseModel):
    doctor_id: uuid.UUID
    doctor_name: str
    department_id: uuid.UUID
    department_name: str
    schedule_date: date
    start_time: str
    end_time: str
    formatted_time: str  # e.g., "09:00 AM – 01:00 PM"
    queue_id: Optional[uuid.UUID] = None
    queue_name: Optional[str] = None
    total_waiting: int = 0

    model_config = ConfigDict(from_attributes=True)


class AvailableDoctorsResponse(BaseModel):
    hospital_id: uuid.UUID
    hospital_name: str
    date: date
    total_doctors_available: int
    doctors: List[AvailableDoctorItem]


class DoctorAvailabilityResponse(BaseModel):
    """Public, schedule-backed availability for one selected doctor."""
    hospital_id: uuid.UUID
    department_id: uuid.UUID
    doctor_id: uuid.UUID
    doctor_name: str
    schedules: List[AvailableDoctorItem]
