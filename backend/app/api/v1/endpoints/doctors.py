"""Doctor endpoints for operational details and date-specific availability scheduling."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import (
    get_current_user,
    require_staff_or_admin,
    verify_staff_hospital_access,
)
from app.models.user import User
from app.models.doctor import Doctor, DoctorStatus
from app.models.doctor_availability import DoctorAvailability

router = APIRouter()


class DoctorDateAvailabilityItem(BaseModel):
    date: date
    is_available: bool
    reason: Optional[str] = None
    is_past: bool = False

    model_config = ConfigDict(from_attributes=True)


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: uuid.UUID
    doctor_name: str
    department_name: str
    hospital_id: uuid.UUID
    hospital_name: str
    availability: List[DoctorDateAvailabilityItem]


class SetDoctorAvailabilityRequest(BaseModel):
    date: date
    is_available: bool
    reason: Optional[str] = None


@router.get("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def get_doctor_availability(
    doctor_id: uuid.UUID,
    days: int = Query(14, ge=1, le=60, description="Number of days to check availability for"),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    """Retrieve date-by-date availability calendar for a doctor."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with ID {doctor_id} not found",
        )

    dept = doctor.department
    hospital = dept.hospital if dept else None

    # Determine date range starting from today in UTC
    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=days)

    # Fetch explicit overrides from database
    overrides = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.availability_date >= today,
            DoctorAvailability.availability_date <= end_date,
        )
        .all()
    )
    overrides_map = {o.availability_date: o for o in overrides}

    items: List[DoctorDateAvailabilityItem] = []
    for offset in range(days):
        d = today + timedelta(days=offset)
        if d in overrides_map:
            rec = overrides_map[d]
            items.append(
                DoctorDateAvailabilityItem(
                    date=d,
                    is_available=rec.is_available,
                    reason=rec.reason,
                    is_past=False,
                )
            )
        else:
            # Default: available (can treat Sundays as unavailable if desired, but default True is standard)
            items.append(
                DoctorDateAvailabilityItem(
                    date=d,
                    is_available=doctor.status == DoctorStatus.AVAILABLE,
                    reason=None,
                    is_past=False,
                )
            )

    return DoctorAvailabilityResponse(
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        department_name=dept.name if dept else "General",
        hospital_id=hospital.id if hospital else uuid.uuid4(),
        hospital_name=hospital.name if hospital else "Hospital",
        availability=items,
    )


@router.post("/{doctor_id}/availability", response_model=DoctorDateAvailabilityItem)
def set_doctor_availability(
    doctor_id: uuid.UUID,
    payload: SetDoctorAvailabilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DoctorDateAvailabilityItem:
    """Staff operation: Set or override doctor availability for a specific calendar date."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor with ID {doctor_id} not found",
        )

    # Verify staff belongs to this doctor's hospital
    hospital_id = doctor.department.hospital_id if doctor.department else None
    if hospital_id:
        verify_staff_hospital_access(current_user, hospital_id)

    today = datetime.now(timezone.utc).date()
    if payload.date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot configure availability for a past date ({payload.date})",
        )

    # Upsert availability record
    record = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.availability_date == payload.date,
        )
        .first()
    )

    if record:
        record.is_available = payload.is_available
        record.reason = payload.reason
    else:
        record = DoctorAvailability(
            doctor_id=doctor_id,
            availability_date=payload.date,
            is_available=payload.is_available,
            reason=payload.reason,
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return DoctorDateAvailabilityItem(
        date=record.availability_date,
        is_available=record.is_available,
        reason=record.reason,
        is_past=False,
    )
