"""Staff doctor scheduling and patient available doctor discovery endpoints."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import require_staff_or_admin, verify_staff_hospital_access, get_current_user
from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.models.doctor import Doctor, DoctorStatus
from app.models.department import Department
from app.models.doctor_schedule import DoctorSchedule
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.schemas.schedule import (
    DoctorScheduleCreateRequest,
    DoctorScheduleUpdateRequest,
    DoctorScheduleBatchRequest,
    DoctorScheduleResponse,
    AvailableDoctorItem,
    AvailableDoctorsResponse,
    DoctorAvailabilityResponse,
    format_time_12h,
)
from app.websocket.manager import connection_manager
from app.services.realtime_dispatcher import safe_run_async

router = APIRouter()


def _broadcast_schedule_change(hospital_id: uuid.UUID, doctor_id: uuid.UUID, sched_date: date, action: str = "SAVED") -> None:
    """Notify connected hospital staff and patient clients that doctor availability changed."""
    try:
        msg = {
            "type": "DOCTOR_SCHEDULE_UPDATED",
            "hospital_id": str(hospital_id),
            "doctor_id": str(doctor_id),
            "schedule_date": sched_date.isoformat(),
            "action": action,
        }
        safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, msg))
    except Exception:
        pass


def _ensure_session_and_queue(
    db: Session,
    doctor: Doctor,
    sched_date: date,
    start_t: time,
    end_t: time,
    status_str: str,
) -> tuple[Optional[OPDSession], Optional[Queue]]:
    """Ensure OPDSession and Queue exist for this doctor and date if status is AVAILABLE."""
    if status_str != "AVAILABLE":
        return None, None

    start_dt = datetime.combine(sched_date, start_t).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(sched_date, end_t).replace(tzinfo=timezone.utc)

    # Find existing session for doctor on this date
    session = (
        db.query(OPDSession)
        .filter(
            OPDSession.doctor_id == doctor.id,
            OPDSession.starts_at >= datetime.combine(sched_date, time(0, 0)).replace(tzinfo=timezone.utc),
            OPDSession.starts_at <= datetime.combine(sched_date, time(23, 59, 59)).replace(tzinfo=timezone.utc),
        )
        .first()
    )

    if not session:
        session = OPDSession(
            doctor_id=doctor.id,
            department_id=doctor.department_id,
            status=SessionStatus.ACTIVE,
            starts_at=start_dt,
            ends_at=end_dt,
        )
        db.add(session)
        db.flush()
    else:
        # Update timings if changed
        session.starts_at = start_dt
        session.ends_at = end_dt
        session.status = SessionStatus.ACTIVE
        db.flush()

    # Find or create the doctor queue record for this specific session and date
    queue = db.query(Queue).filter(Queue.opd_session_id == session.id).first()
    if not queue:
        queue = Queue(
            opd_session_id=session.id,
            name=f"Queue - {doctor.name}",
            queue_date=sched_date,
            status=QueueStatus.ACTIVE,
        )
        db.add(queue)
        db.flush()
    else:
        queue.queue_date = sched_date
        queue.name = f"Queue - {doctor.name}"
        if queue.status != QueueStatus.ACTIVE:
            queue.status = QueueStatus.ACTIVE
        db.flush()

    return session, queue


def _serialize_schedule(sched: DoctorSchedule, db: Session) -> DoctorScheduleResponse:
    """Format DoctorSchedule with appointments count and queue metadata."""
    doc = sched.doctor
    dept = sched.department
    hosp = sched.hospital

    # Count appointments booked for this date and doctor
    queue = None
    if sched.opd_session_id:
        queue = db.query(Queue).filter(Queue.opd_session_id == sched.opd_session_id).first()

    appt_count = 0
    if queue:
        appt_count = (
            db.query(func.count(QueueEntry.id))
            .filter(
                QueueEntry.queue_id == queue.id,
                QueueEntry.appointment_date == sched.schedule_date,
            )
            .scalar()
            or 0
        )

    return DoctorScheduleResponse(
        id=sched.id,
        hospital_id=sched.hospital_id,
        hospital_name=hosp.name if hosp else "Hospital",
        doctor_id=sched.doctor_id,
        doctor_name=doc.name if doc else "Doctor",
        department_id=sched.department_id,
        department_name=dept.name if dept else "General",
        schedule_date=sched.schedule_date,
        start_time=sched.start_time.strftime("%H:%M:%S"),
        end_time=sched.end_time.strftime("%H:%M:%S"),
        start_time_formatted=format_time_12h(sched.start_time),
        end_time_formatted=format_time_12h(sched.end_time),
        status=sched.status,
        appointments_count=appt_count,
        queue_id=queue.id if queue else None,
        queue_status=queue.status.value if queue else None,
    )


@router.post("", response_model=DoctorScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_or_update_schedule(
    payload: DoctorScheduleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DoctorScheduleResponse:
    """Staff operation: Schedule a doctor for a specific date and time range with hospital isolation."""
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be strictly earlier than end time",
        )

    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Doctor {payload.doctor_id} not found")

    # Enforce Staff Hospital Isolation
    hospital_id = doctor.department.hospital_id
    verify_staff_hospital_access(current_user, hospital_id)

    today = datetime.now(timezone.utc).date()
    if payload.schedule_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot schedule doctor for past date ({payload.schedule_date})",
        )

    # Provision OPDSession and Queue if AVAILABLE
    session, queue = _ensure_session_and_queue(
        db=db,
        doctor=doctor,
        sched_date=payload.schedule_date,
        start_t=payload.start_time,
        end_t=payload.end_time,
        status_str=payload.status,
    )

    # Upsert DoctorSchedule record
    sched = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.schedule_date == payload.schedule_date,
        )
        .first()
    )

    if sched:
        sched.start_time = payload.start_time
        sched.end_time = payload.end_time
        sched.status = payload.status
        sched.created_by_staff_id = current_user.id
        if session:
            sched.opd_session_id = session.id
    else:
        sched = DoctorSchedule(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            department_id=doctor.department_id,
            schedule_date=payload.schedule_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            status=payload.status,
            created_by_staff_id=current_user.id,
            opd_session_id=session.id if session else None,
        )
        db.add(sched)

    db.commit()
    db.refresh(sched)
    _broadcast_schedule_change(hospital_id, sched.doctor_id, sched.schedule_date, action="SAVED")
    return _serialize_schedule(sched, db)


@router.post("/batch", response_model=List[DoctorScheduleResponse])
def batch_schedule_doctor(
    payload: DoctorScheduleBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> List[DoctorScheduleResponse]:
    """Staff operation: Plan weekly schedules for a doctor across multiple dates."""
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Doctor {payload.doctor_id} not found")

    hospital_id = doctor.department.hospital_id
    verify_staff_hospital_access(current_user, hospital_id)

    today = datetime.now(timezone.utc).date()
    responses = []

    for item in payload.schedules:
        if item.schedule_date < today:
            continue

        if item.start_time >= item.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Start time must be earlier than end time for date {item.schedule_date}",
            )

        session, queue = _ensure_session_and_queue(
            db=db,
            doctor=doctor,
            sched_date=item.schedule_date,
            start_t=item.start_time,
            end_t=item.end_time,
            status_str=item.status,
        )

        sched = (
            db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor.id,
                DoctorSchedule.schedule_date == item.schedule_date,
            )
            .first()
        )

        if sched:
            sched.start_time = item.start_time
            sched.end_time = item.end_time
            sched.status = item.status
            sched.created_by_staff_id = current_user.id
            if session:
                sched.opd_session_id = session.id
        else:
            sched = DoctorSchedule(
                hospital_id=hospital_id,
                doctor_id=doctor.id,
                department_id=doctor.department_id,
                schedule_date=item.schedule_date,
                start_time=item.start_time,
                end_time=item.end_time,
                status=item.status,
                created_by_staff_id=current_user.id,
                opd_session_id=session.id if session else None,
            )
            db.add(sched)

        db.flush()
        db.refresh(sched)
        responses.append(_serialize_schedule(sched, db))

    db.commit()
    _broadcast_schedule_change(hospital_id, doctor.id, today, action="BATCH_SAVED")
    return responses


@router.get("", response_model=List[DoctorScheduleResponse])
def get_schedules(
    hospital_id: Optional[uuid.UUID] = Query(None),
    doctor_id: Optional[uuid.UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> List[DoctorScheduleResponse]:
    """Staff query: List upcoming schedules filtered by hospital, doctor, or date range.
    Enforces that staff can ONLY view schedules for their assigned hospital.
    """
    query = db.query(DoctorSchedule)

    if current_user.role == UserRole.STAFF:
        if hospital_id and hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Staff members cannot view schedules outside their assigned hospital",
            )
        target_hospital_id = current_user.hospital_id
        query = query.filter(DoctorSchedule.hospital_id == target_hospital_id)

        if doctor_id:
            doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
            if doc and doc.department.hospital_id != target_hospital_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Staff members cannot query schedules for doctors from another hospital",
                )
            query = query.filter(DoctorSchedule.doctor_id == doctor_id)
    else:
        # Admin role
        if hospital_id:
            query = query.filter(DoctorSchedule.hospital_id == hospital_id)
        elif current_user.hospital_id:
            query = query.filter(DoctorSchedule.hospital_id == current_user.hospital_id)
        if doctor_id:
            query = query.filter(DoctorSchedule.doctor_id == doctor_id)

    if start_date:
        query = query.filter(DoctorSchedule.schedule_date >= start_date)
    if end_date:
        query = query.filter(DoctorSchedule.schedule_date <= end_date)

    schedules = query.order_by(DoctorSchedule.schedule_date.asc(), DoctorSchedule.start_time.asc()).all()
    return [_serialize_schedule(s, db) for s in schedules]


@router.put("/{schedule_id}", response_model=DoctorScheduleResponse)
def update_schedule(
    schedule_id: uuid.UUID,
    payload: DoctorScheduleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> DoctorScheduleResponse:
    """Staff operation: Edit an existing scheduled shift for a doctor."""
    sched = db.query(DoctorSchedule).filter(DoctorSchedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor schedule {schedule_id} not found",
        )

    verify_staff_hospital_access(current_user, sched.hospital_id)

    if payload.start_time is not None:
        sched.start_time = payload.start_time
    if payload.end_time is not None:
        sched.end_time = payload.end_time
    if payload.status is not None:
        sched.status = payload.status

    if sched.start_time >= sched.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be strictly earlier than end time",
        )

    # Sync linked session and queue if available
    if sched.opd_session_id:
        session = db.query(OPDSession).filter(OPDSession.id == sched.opd_session_id).first()
        if session:
            session.starts_at = datetime.combine(sched.schedule_date, sched.start_time).replace(tzinfo=timezone.utc)
            session.ends_at = datetime.combine(sched.schedule_date, sched.end_time).replace(tzinfo=timezone.utc)
            if sched.status in ("UNAVAILABLE", "OFF"):
                session.status = SessionStatus.PAUSED
            else:
                session.status = SessionStatus.ACTIVE

    db.commit()
    db.refresh(sched)
    _broadcast_schedule_change(sched.hospital_id, sched.doctor_id, sched.schedule_date, action="UPDATED")
    return _serialize_schedule(sched, db)


@router.delete("/{schedule_id}", status_code=status.HTTP_200_OK)
def delete_schedule(
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Staff operation: Delete or cancel a scheduled doctor shift with hospital isolation."""
    sched = db.query(DoctorSchedule).filter(DoctorSchedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor schedule {schedule_id} not found",
        )

    verify_staff_hospital_access(current_user, sched.hospital_id)

    hosp_id = sched.hospital_id
    doc_id = sched.doctor_id
    s_date = sched.schedule_date
    db.delete(sched)
    db.commit()
    _broadcast_schedule_change(hosp_id, doc_id, s_date, action="DELETED")
    return {"status": "deleted", "schedule_id": str(schedule_id)}


@router.get("/available-doctors", response_model=AvailableDoctorsResponse)
def get_available_doctors_for_date(
    hospital_id: uuid.UUID = Query(..., description="Selected hospital ID"),
    date_val: date = Query(..., alias="date", description="Target consultation date"),
    department_id: Optional[uuid.UUID] = Query(None, description="Optional department filter"),
    db: Session = Depends(get_db),
) -> AvailableDoctorsResponse:
    """Patient discovery: Returns ONLY doctors scheduled as AVAILABLE on the given date with their exact shift timings."""
    if date_val.year < 2000 or date_val.year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date '{date_val}'. Year must be between 2000 and 2100.",
        )
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hospital {hospital_id} not found")

    query = db.query(DoctorSchedule).filter(
        DoctorSchedule.hospital_id == hospital_id,
        DoctorSchedule.schedule_date == date_val,
        DoctorSchedule.status == "AVAILABLE",
    )

    if department_id:
        query = query.filter(DoctorSchedule.department_id == department_id)

    schedules = query.all()

    items: List[AvailableDoctorItem] = []
    for sched in schedules:
        doc = sched.doctor
        dept = sched.department
        queue = None
        if sched.opd_session_id:
            queue = db.query(Queue).filter(Queue.opd_session_id == sched.opd_session_id).first()

        waiting_count = 0
        if queue:
            waiting_count = (
                db.query(func.count(QueueEntry.id))
                .filter(
                    QueueEntry.queue_id == queue.id,
                    QueueEntry.appointment_date == date_val,
                    QueueEntry.status.in_([QueueEntryStatus.BOOKED, QueueEntryStatus.WAITING]),
                )
                .scalar()
                or 0
            )

        formatted_time = f"{format_time_12h(sched.start_time)} – {format_time_12h(sched.end_time)}"

        items.append(
            AvailableDoctorItem(
                doctor_id=sched.doctor_id,
                doctor_name=doc.name if doc else "Doctor",
                department_id=sched.department_id,
                department_name=dept.name if dept else "General",
                schedule_date=sched.schedule_date,
                start_time=sched.start_time.strftime("%H:%M:%S"),
                end_time=sched.end_time.strftime("%H:%M:%S"),
                formatted_time=formatted_time,
                queue_id=queue.id if queue else None,
                queue_name=queue.name if queue else None,
                total_waiting=waiting_count,
            )
        )

    return AvailableDoctorsResponse(
        hospital_id=hospital.id,
        hospital_name=hospital.name,
        date=date_val,
        total_doctors_available=len(items),
        doctors=items,
    )


@router.get("/doctors/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def get_doctor_schedule_availability(
    doctor_id: uuid.UUID,
    hospital_id: Optional[uuid.UUID] = Query(None),
    department_id: Optional[uuid.UUID] = Query(None),
    from_date: date = Query(default_factory=lambda: datetime.now(timezone.utc).date()),
    db: Session = Depends(get_db),
) -> DoctorAvailabilityResponse:
    """Patient doctor-first discovery backed exclusively by active schedules.

    Client hierarchy values are verified against the doctor record so a doctor
    cannot be surfaced under a different hospital or department.
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    department = db.query(Department).filter(Department.id == doctor.department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor has no assigned department")

    resolved_dept_id = department_id or department.id
    resolved_hosp_id = hospital_id or department.hospital_id

    if department.id != resolved_dept_id or department.hospital_id != resolved_hosp_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor does not belong to the selected hospital and department")

    schedules = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.department_id == resolved_dept_id,
        DoctorSchedule.hospital_id == resolved_hosp_id,
        DoctorSchedule.schedule_date >= from_date,
        DoctorSchedule.status.in_(["AVAILABLE", "SCHEDULED"]),
    ).order_by(DoctorSchedule.schedule_date, DoctorSchedule.start_time).all()

    items = []
    for sched in schedules:
        queue = None
        if sched.opd_session_id:
            queue = db.query(Queue).filter(Queue.opd_session_id == sched.opd_session_id).first()
        if not queue:
            queue = (
                db.query(Queue)
                .join(OPDSession, Queue.opd_session_id == OPDSession.id)
                .filter(
                    OPDSession.doctor_id == doctor.id,
                    Queue.queue_date == sched.schedule_date,
                )
                .first()
            )
        if not queue:
            # Automatically provision session and queue for this active schedule
            session, queue = _ensure_session_and_queue(
                db=db,
                doctor=doctor,
                sched_date=sched.schedule_date,
                start_t=sched.start_time,
                end_t=sched.end_time,
                status_str=sched.status,
            )
            sched.opd_session_id = session.id
            db.commit()

        waiting_count = 0
        if queue:
            waiting_count = db.query(func.count(QueueEntry.id)).filter(
                QueueEntry.queue_id == queue.id,
                QueueEntry.appointment_date == sched.schedule_date,
                QueueEntry.status.in_([QueueEntryStatus.BOOKED, QueueEntryStatus.WAITING]),
            ).scalar() or 0
        items.append(AvailableDoctorItem(
            doctor_id=doctor.id, doctor_name=doctor.name,
            department_id=department.id, department_name=department.name,
            schedule_date=sched.schedule_date,
            start_time=sched.start_time.strftime("%H:%M:%S"),
            end_time=sched.end_time.strftime("%H:%M:%S"),
            formatted_time=f"{format_time_12h(sched.start_time)} – {format_time_12h(sched.end_time)}",
            queue_id=queue.id if queue else None,
            queue_name=queue.name if queue else None,
            total_waiting=waiting_count,
        ))
    return DoctorAvailabilityResponse(
        hospital_id=resolved_hosp_id, department_id=resolved_dept_id,
        doctor_id=doctor.id, doctor_name=doctor.name, schedules=items,
    )
