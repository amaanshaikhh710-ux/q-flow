"""Queue management endpoints."""

import uuid
from datetime import date, datetime, time as dt_time, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import (
    get_current_user,
    require_staff_or_admin,
    require_patient,
    get_queue_hospital_id,
    verify_staff_hospital_access,
)
from app.models.user import User
from app.models.queue import Queue, QueueStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.models.queue_entry import QueueEntry
from app.models.queue_entry import PriorityClass
from app.schemas.queue import (
    QueueResponse,
    QueueEntryResponse,
    QueueJoinRequest,
    QueueJoinResponse,
    BookAppointmentRequest,
    CreateQueueRequest,
    StaffBookAppointmentRequest,
    EmergencyInsertRequest,
    DoctorDelayRequest,
    DoctorBreakRequest,
    QueueSnapshotResponse,
)
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from app.websocket.manager import connection_manager
from app.services.realtime_dispatcher import safe_run_async

router = APIRouter()


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/create", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_staff_queue(
    payload: CreateQueueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    """Staff operation: Create a doctor OPD session and queue for a specific date and time window.
    Strictly isolated: Staff can ONLY create queues for doctors in their assigned hospital.
    """
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be strictly earlier than end time",
        )

    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Doctor {payload.doctor_id} not found")

    # Strictly enforce hospital isolation at backend level
    hospital_id = doctor.department.hospital_id
    verify_staff_hospital_access(current_user, hospital_id)

    today = date.today()
    if payload.queue_date.year < 2000 or payload.queue_date.year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid queue_date '{payload.queue_date}'. Year must be between 2000 and 2100.",
        )
    if payload.queue_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create queue for past date ({payload.queue_date.isoformat()})",
        )

    start_dt = datetime.combine(payload.queue_date, payload.start_time).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(payload.queue_date, payload.end_time).replace(tzinfo=timezone.utc)

    # 1. Find or create OPDSession for this doctor and date
    session = (
        db.query(OPDSession)
        .filter(
            OPDSession.doctor_id == doctor.id,
            OPDSession.starts_at >= datetime.combine(payload.queue_date, dt_time.min).replace(tzinfo=timezone.utc),
            OPDSession.starts_at <= datetime.combine(payload.queue_date, dt_time.max).replace(tzinfo=timezone.utc),
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
        session.starts_at = start_dt
        session.ends_at = end_dt
        session.status = SessionStatus.ACTIVE
        db.flush()

    # 2. Find or create Queue for this specific session and date
    queue = db.query(Queue).filter(Queue.opd_session_id == session.id).first()
    if not queue:
        queue = Queue(
            opd_session_id=session.id,
            name=f"Queue - {doctor.name}",
            queue_date=payload.queue_date,
            status=QueueStatus.ACTIVE,
        )
        db.add(queue)
        db.flush()
    else:
        queue.queue_date = payload.queue_date
        queue.name = f"Queue - {doctor.name}"
        if queue.status != QueueStatus.ACTIVE:
            queue.status = QueueStatus.ACTIVE
        db.flush()

    # 3. Create or update authoritative DoctorSchedule record
    sched = (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.schedule_date == payload.queue_date,
        )
        .first()
    )
    if sched:
        sched.start_time = payload.start_time
        sched.end_time = payload.end_time
        sched.status = "AVAILABLE"
        sched.created_by_staff_id = current_user.id
        sched.opd_session_id = session.id
    else:
        sched = DoctorSchedule(
            hospital_id=hospital_id,
            doctor_id=doctor.id,
            department_id=doctor.department_id,
            schedule_date=payload.queue_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            status="AVAILABLE",
            created_by_staff_id=current_user.id,
            opd_session_id=session.id,
        )
        db.add(sched)

    db.commit()
    db.refresh(queue)

    return {
        "queue_id": str(queue.id),
        "queue_date": queue.queue_date.isoformat(),
        "hospital_id": str(hospital_id),
        "department_id": str(doctor.department_id),
        "department_name": doctor.department.name,
        "doctor_id": str(doctor.id),
        "doctor_name": doctor.name,
        "start_time": payload.start_time.strftime("%H:%M"),
        "end_time": payload.end_time.strftime("%H:%M"),
        "status": queue.status.value,
        "message": f"Queue successfully created for Dr. {doctor.name} on {queue.queue_date.isoformat()}",
    }


@router.get("/for-date")
def list_staff_queues_for_date(
    queue_date: date = Query(..., description="Operational queue date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    """Return the authenticated hospital's actual queues and named patients for one date."""
    if queue_date.year < 2000 or queue_date.year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid queue_date '{queue_date}'. Year must be between 2000 and 2100.",
        )
    if current_user.role.value == "staff" and not current_user.hospital_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Staff account has no hospital assignment")
    query = (
        db.query(Queue, OPDSession, Department, Doctor)
        .join(OPDSession, Queue.opd_session_id == OPDSession.id)
        .join(Department, OPDSession.department_id == Department.id)
        .join(Doctor, OPDSession.doctor_id == Doctor.id)
        .filter(Queue.queue_date == queue_date)
    )
    if current_user.role.value == "staff":
        query = query.filter(Department.hospital_id == current_user.hospital_id)

    queues = []
    for queue, session, department, doctor in query.order_by(Doctor.name).all():
        entries = db.query(QueueEntry).filter(
            QueueEntry.queue_id == queue.id,
            QueueEntry.appointment_date == queue_date,
        ).order_by(QueueEntry.token_number).all()

        sched = db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.schedule_date == queue_date,
        ).first()

        start_time_str = sched.start_time.strftime("%H:%M") if sched else (session.starts_at.strftime("%H:%M") if session.starts_at else "09:00")
        end_time_str = sched.end_time.strftime("%H:%M") if sched else (session.ends_at.strftime("%H:%M") if session.ends_at else "13:00")

        queues.append({
            "queue_id": str(queue.id),
            "queue_name": queue.name,
            "queue_date": queue.queue_date.isoformat(),
            "hospital_id": str(department.hospital_id),
            "department_id": str(department.id),
            "department_name": department.name,
            "doctor_id": str(doctor.id),
            "doctor_name": doctor.name,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "status": queue.status.value,
            "entries": [{
                "id": str(entry.id),
                "token_number": entry.token_number,
                "token_display": f"Q{entry.token_number:03d}",
                "patient_name": entry.patient.name if entry.patient else "Patient",
                "patient_phone": entry.patient.phone if entry.patient else None,
                "appointment_time": entry.appointment_time.strftime("%H:%M") if entry.appointment_time else None,
                "booking_source": entry.booking_source,
                "status": entry.status.value,
                "priority_class": entry.priority_class.value if hasattr(entry.priority_class, 'value') else entry.priority_class,
            } for entry in entries],
        })
    return {"queue_date": queue_date.isoformat(), "queues": queues}


@router.post("/book", response_model=QueueJoinResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(
    payload: BookAppointmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
) -> QueueJoinResponse:
    """Patient operation: Book an appointment directly with a doctor on a specific date and time slot."""
    entry = QueueEngineService.join_queue(
        db=db,
        queue_id=payload.queue_id,
        patient_user_id=current_user.id,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        doctor_id=payload.doctor_id,
        hospital_id=payload.hospital_id,
        department_id=payload.department_id,
    )
    try:
        from app.services.reforecast_service import PredictionService
        PredictionService().generate_initial_prediction(db, entry.id)
    except Exception:
        pass

    try:
        msg = {
            "type": "QUEUE_ENTRY_ADDED",
            "queue_id": str(entry.queue_id),
            "entry_id": str(entry.id),
            "token_number": entry.token_number,
            "appointment_date": entry.appointment_date.isoformat(),
        }
        safe_run_async(connection_manager.broadcast_to_queue(entry.queue_id, msg))
        hosp_id = get_queue_hospital_id(db, entry.queue_id)
        if hosp_id:
            safe_run_async(connection_manager.broadcast_to_hospital(hosp_id, msg))
    except Exception:
        pass

    serialized = QueueEngineService.serialize_entry_response(db, entry)
    return QueueJoinResponse(entry=serialized, message="Successfully booked appointment")


@router.post("/{queue_id}/join", response_model=QueueJoinResponse, status_code=status.HTTP_201_CREATED)
def join_queue(
    queue_id: uuid.UUID,
    payload: Optional[QueueJoinRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
) -> QueueJoinResponse:
    """Join the authenticated patient into the target active queue."""
    appointment_date = payload.appointment_date if payload else None
    appointment_time = payload.appointment_time if payload else None
    doctor_id = payload.doctor_id if payload else None
    hospital_id = payload.hospital_id if payload else None
    department_id = payload.department_id if payload else None

    entry = QueueEngineService.join_queue(
        db=db,
        queue_id=queue_id,
        patient_user_id=current_user.id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        department_id=department_id,
    )
    try:
        from app.services.reforecast_service import PredictionService
        PredictionService().generate_initial_prediction(db, entry.id)
    except Exception:
        pass

    try:
        msg = {
            "type": "QUEUE_ENTRY_ADDED",
            "queue_id": str(entry.queue_id),
            "entry_id": str(entry.id),
            "token_number": entry.token_number,
            "appointment_date": entry.appointment_date.isoformat(),
        }
        safe_run_async(connection_manager.broadcast_to_queue(entry.queue_id, msg))
        hosp_id = get_queue_hospital_id(db, entry.queue_id)
        if hosp_id:
            safe_run_async(connection_manager.broadcast_to_hospital(hosp_id, msg))
    except Exception:
        pass

    serialized = QueueEngineService.serialize_entry_response(db, entry)
    return QueueJoinResponse(entry=serialized, message="Successfully joined queue")


@router.post("/{queue_id}/staff-book", response_model=QueueJoinResponse, status_code=status.HTTP_201_CREATED)
def staff_book_patient(
    queue_id: uuid.UUID,
    payload: StaffBookAppointmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueJoinResponse:
    """Staff operation: Book a walk-in, phone, or reception patient into the target active queue."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry = QueueEngineService.staff_book_appointment(
        db=db,
        queue_id=queue_id,
        staff_user_id=current_user.id,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        booking_source=payload.booking_source,
        priority_class=payload.priority_class or PriorityClass.NORMAL,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        notes=payload.notes,
    )

    try:
        from app.services.reforecast_service import PredictionService
        PredictionService().generate_initial_prediction(db, entry.id)
    except Exception:
        pass

    try:
        msg = {
            "type": "QUEUE_ENTRY_ADDED",
            "queue_id": str(entry.queue_id),
            "entry_id": str(entry.id),
            "token_number": entry.token_number,
            "appointment_date": entry.appointment_date.isoformat(),
        }
        safe_run_async(connection_manager.broadcast_to_queue(entry.queue_id, msg))
        safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, msg))
    except Exception:
        pass

    serialized = QueueEngineService.serialize_entry_response(db, entry)
    return QueueJoinResponse(entry=serialized, message="Successfully booked appointment")


@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueueResponse:
    """Get metadata for a specific queue."""
    if current_user.role.value == "staff":
        hospital_id = get_queue_hospital_id(db, queue_id)
        verify_staff_hospital_access(current_user, hospital_id)

    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue with ID {queue_id} does not exist",
        )
    return queue


@router.get("/{queue_id}/snapshot", response_model=QueueSnapshotResponse)
def get_queue_snapshot(
    queue_id: uuid.UUID,
    target_date: Optional[date] = Query(None, description="Optional date filter for snapshot (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueueSnapshotResponse:
    """Get authoritative current state, serving patient, next in line, and active waiting list."""
    if target_date is not None and (target_date.year < 2000 or target_date.year > 2100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target_date '{target_date}'. Year must be between 2000 and 2100.",
        )
    if current_user.role.value == "staff":
        hospital_id = get_queue_hospital_id(db, queue_id)
        verify_staff_hospital_access(current_user, hospital_id)

    snapshot_data = QueueEngineService.get_queue_snapshot(db, queue_id, target_date=target_date)
    return QueueSnapshotResponse(**snapshot_data)


@router.post("/{queue_id}/call-next", response_model=QueueEntryResponse)
def call_next_patient(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Determine and call the next eligible waiting patient."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.call_next_patient(
        db=db,
        queue_id=queue_id,
        actor_id=current_user.id,
    )
    return QueueEngineService.serialize_entry_response(db, entry, position=0)


@router.post("/{queue_id}/emergency", response_model=QueueEntryResponse, status_code=status.HTTP_201_CREATED)
def insert_emergency_patient(
    queue_id: uuid.UUID,
    payload: EmergencyInsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Atomically insert an emergency patient into the queue."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.insert_emergency(
        db=db,
        queue_id=queue_id,
        patient_user_id=payload.patient_user_id,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    return QueueEngineService.serialize_entry_response(db, entry)


@router.post("/{queue_id}/pause", response_model=QueueResponse)
def pause_queue(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueResponse:
    """Staff operation: Pause queue operations."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    return QueueStateMachineService.pause_queue(
        db=db,
        queue_id=queue_id,
        actor_id=current_user.id,
    )


@router.post("/{queue_id}/resume", response_model=QueueResponse)
def resume_queue(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueResponse:
    """Staff operation: Resume paused queue."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    return QueueStateMachineService.resume_queue(
        db=db,
        queue_id=queue_id,
        actor_id=current_user.id,
    )


@router.post("/{queue_id}/end", response_model=QueueResponse)
def end_queue(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueResponse:
    """Staff operation: End and complete the queue."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    return QueueStateMachineService.end_queue(
        db=db,
        queue_id=queue_id,
        actor_id=current_user.id,
    )


@router.post("/{queue_id}/doctor-delay", response_model=Dict[str, Any])
def report_doctor_delay(
    queue_id: uuid.UUID,
    payload: DoctorDelayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    """Staff operation: Record an operational delay for the doctor."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    event = QueueStateMachineService.record_doctor_delay(
        db=db,
        queue_id=queue_id,
        delay_minutes=payload.delay_minutes,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    try:
        from app.services.reforecast_service import PredictionService
        PredictionService().reforecast_after_event(db, queue_id, event.id)
    except Exception:
        pass

    return {
        "success": True,
        "event_id": str(event.id),
        "event_type": event.event_type,
        "delay_minutes": payload.delay_minutes,
        "reason": payload.reason,
        "recorded_at": event.event_time.isoformat(),
    }


@router.post("/{queue_id}/doctor-break/start", response_model=Dict[str, Any])
def start_doctor_break(
    queue_id: uuid.UUID,
    payload: DoctorBreakRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    """Staff operation: Record doctor break start."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    event = QueueStateMachineService.record_doctor_break_start(
        db=db,
        queue_id=queue_id,
        duration_minutes=payload.duration_minutes,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    return {
        "success": True,
        "event_id": str(event.id),
        "event_type": event.event_type,
        "estimated_duration_minutes": payload.duration_minutes,
        "recorded_at": event.event_time.isoformat(),
    }


@router.post("/{queue_id}/doctor-break/end", response_model=Dict[str, Any])
def end_doctor_break(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    """Staff operation: Record doctor break conclusion."""
    hospital_id = get_queue_hospital_id(db, queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    event = QueueStateMachineService.record_doctor_break_end(
        db=db,
        queue_id=queue_id,
        actor_id=current_user.id,
    )
    return {
        "success": True,
        "event_id": str(event.id),
        "event_type": event.event_type,
        "recorded_at": event.event_time.isoformat(),
    }
