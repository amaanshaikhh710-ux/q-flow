"""Queue entry management endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone, timedelta
from typing import List
from app.core.database import get_db
from app.api.deps import (
    get_current_user,
    require_staff_or_admin,
    require_patient,
    get_queue_hospital_id,
    verify_staff_hospital_access,
)
from app.models.user import User, UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.schemas.queue import (
    QueueEntryResponse,
    PriorityUpdateRequest,
    ConsultationCompleteRequest,
    NoShowRequest,
    TemporaryLeaveRequest,
    RequeueRequest,
    PatientAppointmentItem,
    PatientAppointmentsResponse,
)
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService

router = APIRouter()


def get_entry_or_404(db: Session, entry_id: uuid.UUID) -> QueueEntry:
    """Helper to retrieve entry or raise 404."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )
    return entry


@router.get("/my", response_model=PatientAppointmentsResponse)
def get_my_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
) -> PatientAppointmentsResponse:
    """Patient operation: Return all appointments belonging to the logged-in patient."""
    from sqlalchemy.orm import joinedload
    from app.models.queue import Queue
    from app.models.opd_session import OPDSession
    from app.models.department import Department
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.prediction_snapshot import PredictionSnapshot
    from app.models.arrival_plan import ArrivalPlan

    entries = (
        db.query(QueueEntry)
        .options(
            joinedload(QueueEntry.queue)
            .joinedload(Queue.opd_session)
            .joinedload(OPDSession.department)
            .joinedload(Department.hospital),
            joinedload(QueueEntry.queue)
            .joinedload(Queue.opd_session)
            .joinedload(OPDSession.doctor),
        )
        .filter(QueueEntry.patient_user_id == current_user.id)
        .order_by(QueueEntry.created_at.desc())
        .all()
    )

    today_list: List[PatientAppointmentItem] = []
    upcoming_list: List[PatientAppointmentItem] = []
    past_list: List[PatientAppointmentItem] = []

    IST = timezone(timedelta(hours=5, minutes=30))
    today_date = datetime.now(timezone.utc).astimezone(IST).date()

    for entry in entries:
        queue = entry.queue
        opd_session = queue.opd_session if queue else None
        dept = opd_session.department if opd_session else None
        hosp = dept.hospital if dept else None
        doc = opd_session.doctor if opd_session else None

        position = QueueEngineService.get_entry_position(db, entry)

        latest_pred = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(PredictionSnapshot.created_at.desc())
            .first()
        )
        if not latest_pred and entry.status in (QueueEntryStatus.BOOKED, QueueEntryStatus.WAITING, QueueEntryStatus.ARRIVED):
            try:
                from app.services.reforecast_service import PredictionService
                latest_pred = PredictionService().generate_initial_prediction(db, entry.id)
            except Exception:
                pass

        latest_plan = (
            db.query(ArrivalPlan)
            .filter(ArrivalPlan.queue_entry_id == entry.id)
            .order_by(ArrivalPlan.created_at.desc())
            .first()
        )

        est_wait = None
        est_start = None
        latest_dep = None
        travel_dur = None
        travel_unc = None
        travel_st = "UNAVAILABLE"

        if latest_pred:
            est_start = latest_pred.predicted_start_at
            if est_start:
                now_utc = datetime.now(timezone.utc)
                s_time = est_start if est_start.tzinfo is not None else est_start.replace(tzinfo=timezone.utc)
                est_wait = max(0, int((s_time - now_utc).total_seconds() / 60))

        if latest_plan:
            latest_dep = latest_plan.departure_start_at or latest_plan.departure_end_at
            if latest_plan.travel_duration_seconds:
                travel_dur = int(round(latest_plan.travel_duration_seconds / 60))
            if latest_plan.travel_uncertainty_seconds:
                travel_unc = int(round(latest_plan.travel_uncertainty_seconds / 60))
            travel_st = latest_plan.travel_status

        item = PatientAppointmentItem(
            id=entry.id,
            queue_id=entry.queue_id,
            token_number=entry.token_number,
            token_display=f"Q{entry.token_number:03d}",
            status=entry.status,
            priority_class=entry.priority_class,
            booking_source=getattr(entry, "booking_source", "ONLINE") or "ONLINE",
            notes=getattr(entry, "notes", None),
            joined_at=entry.joined_at,
            arrived_at=entry.arrived_at,
            called_at=entry.called_at,
            position=position,
            appointment_date=entry.appointment_date,
            hospital_id=hosp.id if hosp else uuid.UUID(int=0),
            hospital_name=hosp.name if hosp else "Unknown Hospital",
            hospital_address=hosp.address if hosp else None,
            hospital_latitude=float(hosp.latitude) if hosp and hosp.latitude else None,
            hospital_longitude=float(hosp.longitude) if hosp and hosp.longitude else None,
            department_id=dept.id if dept else uuid.UUID(int=0),
            department_name=dept.name if dept else "General",
            doctor_id=doc.id if doc else uuid.UUID(int=0),
            doctor_name=doc.name if doc else "Doctor On Duty",
            estimated_wait_minutes=est_wait,
            estimated_start_time=est_start,
            latest_departure_time=latest_dep,
            travel_duration_minutes=travel_dur,
            travel_uncertainty_minutes=travel_unc,
            travel_mode=entry.travel_mode or "DRIVE",
            travel_status=travel_st,
            created_at=entry.created_at,
        )

        entry_date = entry.appointment_date or (entry.joined_at.date() if entry.joined_at else entry.created_at.date())

        if entry.status in (QueueEntryStatus.COMPLETED, QueueEntryStatus.NO_SHOW):
            past_list.append(item)
        elif entry_date == today_date:
            today_list.append(item)
        elif entry_date > today_date:
            upcoming_list.append(item)
        else:
            past_list.append(item)

    return PatientAppointmentsResponse(
        today=today_list,
        upcoming=upcoming_list,
        past=past_list,
        total=len(entries),
    )


@router.get("/{entry_id}", response_model=QueueEntryResponse)
def get_queue_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueueEntryResponse:
    """Get authoritative entry details and position.

    Patients can only view their own entry; staff/admin can view any within their hospital.
    """
    entry = get_entry_or_404(db, entry_id)
    if current_user.role == UserRole.PATIENT and entry.patient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot access queue entries belonging to other patients",
        )
    if current_user.role == UserRole.STAFF:
        hospital_id = get_queue_hospital_id(db, entry.queue_id)
        verify_staff_hospital_access(current_user, hospital_id)

    return QueueEngineService.serialize_entry_response(db, entry)


@router.post("/{entry_id}/arrive", response_model=QueueEntryResponse)
def mark_patient_arrived(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Mark patient physically arrived at the hospital."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.mark_arrived(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
    )
    return QueueEngineService.serialize_entry_response(db, entry)


@router.post("/{entry_id}/wait", response_model=QueueEntryResponse)
def mark_patient_waiting(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Move an arrived patient into active WAITING line."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.mark_waiting(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
    )
    return QueueEngineService.serialize_entry_response(db, entry)


@router.post("/{entry_id}/call", response_model=QueueEntryResponse)
def call_patient(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Call a specific patient."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.call_patient(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
    )
    return QueueEngineService.serialize_entry_response(db, entry, position=0)


@router.post("/{entry_id}/start-consultation", response_model=QueueEntryResponse)
def start_consultation(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Transition patient to IN_CONSULTATION and record consultation start."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    QueueStateMachineService.start_consultation(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
    )
    entry = get_entry_or_404(db, entry_id)
    return QueueEngineService.serialize_entry_response(db, entry, position=0)


@router.post("/{entry_id}/complete-consultation", response_model=QueueEntryResponse)
def complete_consultation(
    entry_id: uuid.UUID,
    payload: ConsultationCompleteRequest = ConsultationCompleteRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Transition patient to COMPLETED and record clinical duration."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    QueueStateMachineService.complete_consultation(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
        interruption_notes=payload.interruption_notes,
    )
    entry = get_entry_or_404(db, entry_id)
    return QueueEngineService.serialize_entry_response(db, entry, position=None)


@router.post("/{entry_id}/no-show", response_model=QueueEntryResponse)
def mark_no_show(
    entry_id: uuid.UUID,
    payload: NoShowRequest = NoShowRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Mark patient as NO_SHOW."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.mark_no_show(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    return QueueEngineService.serialize_entry_response(db, entry, position=None)


@router.post("/{entry_id}/leave", response_model=QueueEntryResponse)
def patient_leave(
    entry_id: uuid.UUID,
    payload: TemporaryLeaveRequest = TemporaryLeaveRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff/Admin operation: Record temporary absence (WAITING -> TEMPORARILY_LEFT)."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    updated_entry, _ = QueueStateMachineService.temporary_leave(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    return QueueEngineService.serialize_entry_response(db, updated_entry, position=None)


@router.post("/{entry_id}/return", response_model=QueueEntryResponse)
def patient_return(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff/Admin operation: Record patient return (TEMPORARILY_LEFT -> RETURNED). Awaits staff re-queueing (DEC-033)."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    updated_entry = QueueStateMachineService.return_patient(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
    )
    return QueueEngineService.serialize_entry_response(db, updated_entry, position=None)


@router.post("/{entry_id}/requeue", response_model=QueueEntryResponse)
def staff_requeue_patient(
    entry_id: uuid.UUID,
    payload: RequeueRequest = RequeueRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff-managed re-queueing of a RETURNED patient into active WAITING state (DEC-033)."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.requeue_patient(
        db=db,
        entry_id=entry_id,
        actor_id=current_user.id,
        priority_class=payload.priority_class,
        reason=payload.reason,
    )
    return QueueEngineService.serialize_entry_response(db, entry)


@router.post("/{entry_id}/priority", response_model=QueueEntryResponse)
def change_entry_priority(
    entry_id: uuid.UUID,
    payload: PriorityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> QueueEntryResponse:
    """Staff operation: Change patient priority class."""
    entry = get_entry_or_404(db, entry_id)
    hospital_id = get_queue_hospital_id(db, entry.queue_id)
    verify_staff_hospital_access(current_user, hospital_id)

    entry, _ = QueueStateMachineService.change_priority(
        db=db,
        entry_id=entry_id,
        new_priority=payload.priority_class,
        actor_id=current_user.id,
        reason=payload.reason,
    )
    return QueueEngineService.serialize_entry_response(db, entry)
