"""Hospital Historical Reporting, Filtering, and Data Export Endpoints."""

import csv
import io
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_

from app.core.database import get_db
from app.api.deps import get_current_user, require_staff
from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.opd_session import OPDSession
from app.models.queue import Queue
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.consultation import Consultation
from app.schemas.historical import (
    HistoricalAppointmentItem,
    HistoricalAppointmentsResponse,
)
from app.services.queue_engine import format_token

router = APIRouter(prefix="/hospital", tags=["Hospital Historical Reports"])


def resolve_date_range(
    date_preset: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Resolve date range filter based on preset or explicit start/end dates."""
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(now.date(), time.max).replace(tzinfo=timezone.utc)

    if date_preset == "today":
        return today_start, today_end
    elif date_preset == "yesterday":
        yesterday_date = now.date() - timedelta(days=1)
        return (
            datetime.combine(yesterday_date, time.min).replace(tzinfo=timezone.utc),
            datetime.combine(yesterday_date, time.max).replace(tzinfo=timezone.utc),
        )
    elif date_preset == "this_week":
        # Monday of current week
        monday = now.date() - timedelta(days=now.weekday())
        return (
            datetime.combine(monday, time.min).replace(tzinfo=timezone.utc),
            today_end,
        )
    elif date_preset == "last_week":
        # Monday to Sunday of previous week
        monday_last = now.date() - timedelta(days=now.weekday() + 7)
        sunday_last = monday_last + timedelta(days=6)
        return (
            datetime.combine(monday_last, time.min).replace(tzinfo=timezone.utc),
            datetime.combine(sunday_last, time.max).replace(tzinfo=timezone.utc),
        )
    elif date_preset == "this_month":
        first_of_month = now.date().replace(day=1)
        return (
            datetime.combine(first_of_month, time.min).replace(tzinfo=timezone.utc),
            today_end,
        )
    elif date_preset == "custom" or (start_date or end_date):
        resolved_start = start_date
        resolved_end = end_date
        if resolved_start and resolved_start.tzinfo is None:
            resolved_start = resolved_start.replace(tzinfo=timezone.utc)
        if resolved_end and resolved_end.tzinfo is None:
            resolved_end = resolved_end.replace(tzinfo=timezone.utc)
        return resolved_start, resolved_end

    return None, None


def build_historical_query(
    db: Session,
    target_hospital_id: uuid.UUID,
    date_preset: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    doctor_id: Optional[uuid.UUID] = None,
    department_id: Optional[uuid.UUID] = None,
    queue_id: Optional[uuid.UUID] = None,
    entry_status: Optional[str] = None,
    booking_source: Optional[str] = None,
):
    """Construct filtered SQLAlchemy query scoped to the hospital."""
    query = (
        db.query(
            QueueEntry,
            Queue,
            OPDSession,
            Department,
            Doctor,
            User,
            Consultation,
        )
        .join(Queue, QueueEntry.queue_id == Queue.id)
        .join(OPDSession, Queue.opd_session_id == OPDSession.id)
        .join(Department, OPDSession.department_id == Department.id)
        .join(Doctor, OPDSession.doctor_id == Doctor.id)
        .outerjoin(User, QueueEntry.patient_user_id == User.id)
        .outerjoin(Consultation, Consultation.queue_entry_id == QueueEntry.id)
        .filter(Department.hospital_id == target_hospital_id)
    )

    # Date range filtering
    range_start, range_end = resolve_date_range(date_preset, start_date, end_date)
    if range_start:
        query = query.filter(QueueEntry.joined_at >= range_start)
    if range_end:
        query = query.filter(QueueEntry.joined_at <= range_end)

    # Doctor filter
    if doctor_id:
        query = query.filter(Doctor.id == doctor_id)

    # Department filter
    if department_id:
        query = query.filter(Department.id == department_id)

    # Queue filter
    if queue_id:
        query = query.filter(Queue.id == queue_id)

    # Status filter
    if entry_status:
        query = query.filter(QueueEntry.status == entry_status)

    # Booking source filter
    if booking_source:
        query = query.filter(QueueEntry.booking_source == booking_source)

    return query


@router.get(
    "/historical-appointments",
    response_model=HistoricalAppointmentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Filtered Historical Hospital Appointments",
    description="Returns filtered and paginated operational appointment records for the staff member's assigned hospital.",
)
def get_historical_appointments(
    date_preset: Optional[str] = Query(None, description="Date preset: today, yesterday, this_week, last_week, this_month, custom"),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    doctor_id: Optional[uuid.UUID] = Query(None, description="Filter by doctor ID"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by department ID"),
    queue_id: Optional[uuid.UUID] = Query(None, description="Filter by queue ID"),
    status: Optional[str] = Query(None, description="Filter by entry status (e.g. COMPLETED, NO_SHOW)"),
    booking_source: Optional[str] = Query(None, description="Filter by booking source (ONLINE, PHONE, WALK_IN, STAFF)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    hospital_id: Optional[uuid.UUID] = Query(None, description="Admin hospital selector"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
) -> HistoricalAppointmentsResponse:
    # Hospital scoping
    target_hospital_id = current_user.hospital_id
    if current_user.role == UserRole.ADMIN and hospital_id:
        target_hospital_id = hospital_id

    if not target_hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff user has no assigned hospital",
        )

    query = build_historical_query(
        db=db,
        target_hospital_id=target_hospital_id,
        date_preset=date_preset,
        start_date=start_date,
        end_date=end_date,
        doctor_id=doctor_id,
        department_id=department_id,
        queue_id=queue_id,
        entry_status=status,
        booking_source=booking_source,
    )

    total_count = query.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    records = (
        query.order_by(desc(QueueEntry.joined_at), desc(QueueEntry.token_number))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[HistoricalAppointmentItem] = []
    for entry, q, session, dept, doc, patient, consult in records:
        # Patient name & phone
        p_name = patient.name if patient else "Walk-in Patient"
        p_phone = patient.phone if patient else None

        # Duration calculation
        duration_sec = None
        duration_min = None
        if consult and consult.duration_seconds is not None:
            duration_sec = consult.duration_seconds
            duration_min = round(duration_sec / 60.0, 1)
        elif consult and consult.started_at and consult.completed_at:
            duration_sec = int((consult.completed_at - consult.started_at).total_seconds())
            duration_min = round(duration_sec / 60.0, 1)

        # Waiting time calculation (arrived/joined to consultation started)
        wait_sec = None
        wait_min = None
        arrival_ref = entry.arrived_at or entry.joined_at
        consult_start = consult.started_at if consult else None
        if consult_start and arrival_ref:
            wait_sec = max(0, int((consult_start - arrival_ref).total_seconds()))
            wait_min = round(wait_sec / 60.0, 1)

        items.append(
            HistoricalAppointmentItem(
                id=entry.id,
                token_number=entry.token_number,
                token_display=format_token(entry.token_number),
                date=entry.joined_at,
                booking_source=entry.booking_source or "ONLINE",
                doctor_id=doc.id,
                doctor_name=doc.name,
                department_id=dept.id,
                department_name=dept.name,
                queue_id=q.id,
                queue_name=q.name,
                patient_name=p_name,
                patient_phone=p_phone,
                arrived_at=entry.arrived_at,
                consultation_started_at=consult.started_at if consult else None,
                consultation_completed_at=consult.completed_at if consult else None,
                consultation_duration_seconds=duration_sec,
                consultation_duration_minutes=duration_min,
                waiting_time_seconds=wait_sec,
                waiting_time_minutes=wait_min,
                status=entry.status.value if hasattr(entry.status, "value") else str(entry.status),
                notes=entry.notes,
            )
        )

    return HistoricalAppointmentsResponse(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/historical-appointments/export",
    summary="Export Filtered Historical Appointments as CSV",
    description="Streams a CSV export containing strictly the filtered records matching criteria for the staff member's assigned hospital.",
)
def export_historical_appointments(
    date_preset: Optional[str] = Query(None, description="Date preset: today, yesterday, this_week, last_week, this_month, custom"),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    doctor_id: Optional[uuid.UUID] = Query(None, description="Filter by doctor ID"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by department ID"),
    queue_id: Optional[uuid.UUID] = Query(None, description="Filter by queue ID"),
    status: Optional[str] = Query(None, description="Filter by entry status"),
    booking_source: Optional[str] = Query(None, description="Filter by booking source"),
    hospital_id: Optional[uuid.UUID] = Query(None, description="Admin hospital selector"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    target_hospital_id = current_user.hospital_id
    if current_user.role == UserRole.ADMIN and hospital_id:
        target_hospital_id = hospital_id

    if not target_hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff user has no assigned hospital",
        )

    query = build_historical_query(
        db=db,
        target_hospital_id=target_hospital_id,
        date_preset=date_preset,
        start_date=start_date,
        end_date=end_date,
        doctor_id=doctor_id,
        department_id=department_id,
        queue_id=queue_id,
        entry_status=status,
        booking_source=booking_source,
    )

    records = (
        query.order_by(desc(QueueEntry.joined_at), desc(QueueEntry.token_number))
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Token Number",
        "Date",
        "Booking Source",
        "Patient Name",
        "Patient Phone",
        "Department",
        "Doctor",
        "Queue Name",
        "Arrival Time",
        "Consultation Start",
        "Consultation End",
        "Duration (Minutes)",
        "Waiting Time (Minutes)",
        "Status",
        "Notes",
    ])

    for entry, q, session, dept, doc, patient, consult in records:
        p_name = patient.name if patient else "Walk-in Patient"
        p_phone = patient.phone if patient else ""

        duration_min = ""
        if consult and consult.duration_seconds is not None:
            duration_min = str(round(consult.duration_seconds / 60.0, 1))
        elif consult and consult.started_at and consult.completed_at:
            duration_min = str(round((consult.completed_at - consult.started_at).total_seconds() / 60.0, 1))

        wait_min = ""
        arrival_ref = entry.arrived_at or entry.joined_at
        consult_start = consult.started_at if consult else None
        if consult_start and arrival_ref:
            wait_min = str(round(max(0, (consult_start - arrival_ref).total_seconds()) / 60.0, 1))

        writer.writerow([
            format_token(entry.token_number),
            entry.joined_at.strftime("%Y-%m-%d %H:%M:%S") if entry.joined_at else "",
            entry.booking_source or "ONLINE",
            p_name,
            p_phone,
            dept.name,
            doc.name,
            q.name,
            entry.arrived_at.strftime("%Y-%m-%d %H:%M:%S") if entry.arrived_at else "",
            consult.started_at.strftime("%Y-%m-%d %H:%M:%S") if (consult and consult.started_at) else "",
            consult.completed_at.strftime("%Y-%m-%d %H:%M:%S") if (consult and consult.completed_at) else "",
            duration_min,
            wait_min,
            entry.status.value if hasattr(entry.status, "value") else str(entry.status),
            entry.notes or "",
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"qflow_historical_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
