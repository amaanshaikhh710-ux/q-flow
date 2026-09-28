"""Read-only discovery endpoints for Hospital, Department, Doctor, and OPD Session listing.

These endpoints are public (no auth required) and allow patients to browse
the healthcare provider hierarchy before joining a queue.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.api.deps import require_staff_or_admin
from app.models.user import User
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus

router = APIRouter(prefix="/discovery", tags=["discovery"])


# ---------------------------------------------------------------------------
# Response schemas (discovery-specific, lightweight)
# ---------------------------------------------------------------------------

class HospitalBrief(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentBrief(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class DoctorBrief(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    status: DoctorStatus

    model_config = ConfigDict(from_attributes=True)


class ActiveQueueBrief(BaseModel):
    id: uuid.UUID
    name: str
    status: QueueStatus
    total_waiting: int

    model_config = ConfigDict(from_attributes=True)


class OPDSessionBrief(BaseModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID
    status: SessionStatus
    starts_at: datetime
    ends_at: Optional[datetime] = None
    active_queue: Optional[ActiveQueueBrief] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# GET /api/v1/discovery/hospitals
# ---------------------------------------------------------------------------

@router.get(
    "/hospitals",
    response_model=List[HospitalBrief],
    summary="List All Hospitals",
    description="Public endpoint. Returns all registered hospitals.",
)
def list_hospitals(db: Session = Depends(get_db)) -> List[HospitalBrief]:
    hospitals = db.query(Hospital).order_by(Hospital.name).all()
    return [HospitalBrief.model_validate(h) for h in hospitals]


# ---------------------------------------------------------------------------
# GET /api/v1/discovery/hospitals/{hospital_id}/departments
# ---------------------------------------------------------------------------

@router.get(
    "/hospitals/{hospital_id}/departments",
    response_model=List[DepartmentBrief],
    summary="List Departments in a Hospital",
    description="Public endpoint. Returns all departments belonging to the given hospital.",
)
def list_departments(
    hospital_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[DepartmentBrief]:
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hospital {hospital_id} not found.",
        )
    departments = (
        db.query(Department)
        .filter(Department.hospital_id == hospital_id)
        .order_by(Department.name)
        .all()
    )
    return [DepartmentBrief.model_validate(d) for d in departments]


# ---------------------------------------------------------------------------
# GET /api/v1/discovery/departments/{department_id}/doctors
# ---------------------------------------------------------------------------

@router.get(
    "/departments/{department_id}/doctors",
    response_model=List[DoctorBrief],
    summary="List Doctors in a Department",
    description="Public endpoint. Returns all doctors belonging to the given department.",
)
def list_doctors(
    department_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[DoctorBrief]:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department {department_id} not found.",
        )
    doctors = (
        db.query(Doctor)
        .filter(Doctor.department_id == department_id)
        .order_by(Doctor.name)
        .all()
    )
    return [DoctorBrief.model_validate(d) for d in doctors]


# ---------------------------------------------------------------------------
# GET /api/v1/discovery/doctors/{doctor_id}/sessions
# ---------------------------------------------------------------------------

@router.get(
    "/doctors/{doctor_id}/sessions",
    response_model=List[OPDSessionBrief],
    summary="List Active OPD Sessions for a Doctor",
    description=(
        "Public endpoint. Returns ACTIVE and SCHEDULED OPD sessions for a doctor, "
        "including any associated active queue with waiting count."
    ),
)
def list_doctor_sessions(
    doctor_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[OPDSessionBrief]:
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor {doctor_id} not found.",
        )

    sessions = (
        db.query(OPDSession)
        .options(joinedload(OPDSession.queues))
        .filter(
            OPDSession.doctor_id == doctor_id,
            OPDSession.status.in_([SessionStatus.ACTIVE, SessionStatus.SCHEDULED]),
        )
        .order_by(OPDSession.starts_at)
        .all()
    )

    result: List[OPDSessionBrief] = []
    for session in sessions:
        # Find the first active or paused queue for this session
        active_queue: Optional[ActiveQueueBrief] = None
        for q in session.queues:
            if q.status in (QueueStatus.ACTIVE, QueueStatus.PAUSED):
                # Count waiting entries
                from app.models.queue_entry import QueueEntry, QueueEntryStatus
                waiting_count = (
                    db.query(QueueEntry)
                    .filter(
                        QueueEntry.queue_id == q.id,
                        QueueEntry.status == QueueEntryStatus.WAITING,
                    )
                    .count()
                )
                active_queue = ActiveQueueBrief(
                    id=q.id,
                    name=q.name,
                    status=q.status,
                    total_waiting=waiting_count,
                )
                break

        result.append(
            OPDSessionBrief(
                id=session.id,
                doctor_id=session.doctor_id,
                department_id=session.department_id,
                status=session.status,
                starts_at=session.starts_at,
                ends_at=session.ends_at,
                active_queue=active_queue,
            )
        )

    return result


# ---------------------------------------------------------------------------
# GET /api/v1/discovery/staff-hospital
# ---------------------------------------------------------------------------

@router.get(
    "/staff-hospital",
    summary="Get Assigned Hospital for Staff Member",
    description="Returns the hospital and departments assigned to the authenticated staff member.",
)
def get_staff_hospital(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
) -> Dict[str, Any]:
    # SECURITY: Never trust any client-supplied hospital_id.
    # The hospital context is derived exclusively from the authenticated staff user's
    # assigned hospital_id. A staff member cannot query another hospital's data
    # by supplying a different hospital_id parameter.
    target_hospital_id = current_user.hospital_id

    # Admin fallback: if admin has no hospital assigned, pick the first hospital.
    if not target_hospital_id and current_user.role.value == "admin":
        first_hosp = db.query(Hospital).order_by(Hospital.name).first()
        if first_hosp:
            target_hospital_id = first_hosp.id

    if not target_hospital_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No hospital is assigned to this staff account. Contact your administrator.",
        )

    hospital = db.query(Hospital).filter(Hospital.id == target_hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned hospital not found.",
        )

    departments = (
        db.query(Department)
        .filter(Department.hospital_id == target_hospital_id)
        .order_by(Department.name)
        .all()
    )

    # Get all active sessions and queues for this hospital
    from datetime import datetime, timezone
    from app.models.queue_entry import QueueEntry, QueueEntryStatus
    from app.models.queue import Queue, QueueStatus
    from app.models.queue_event import QueueEvent, QueueEventType
    from app.models.opd_session import OPDSession, SessionStatus
    from app.models.consultation import Consultation

    dept_ids = [d.id for d in departments]
    dept_dict = {d.id: d for d in departments}
    doctors = db.query(Doctor).filter(Doctor.department_id.in_(dept_ids)).all() if dept_ids else []
    doc_dict = {d.id: d for d in doctors}

    # Retrieve all queues for this hospital's departments
    all_hospital_queues = (
        db.query(Queue)
        .join(OPDSession, Queue.opd_session_id == OPDSession.id)
        .filter(OPDSession.department_id.in_(dept_ids))
        .all()
    ) if dept_ids else []
    all_queue_ids = [q.id for q in all_hospital_queues]

    # Calculate real operational metrics for today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    today_appointments = 0
    waiting_patients = 0
    in_consultation = 0
    completed_consultations = 0
    no_shows = 0
    doctor_delays = 0
    emergency_events = 0
    active_queues_count = sum(1 for q in all_hospital_queues if q.status == QueueStatus.ACTIVE)

    if all_queue_ids:
        # Today's appointments (joined or created today)
        today_appointments = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(all_queue_ids),
                QueueEntry.joined_at >= today_start,
            )
            .count()
        )
        # Currently waiting
        waiting_patients = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(all_queue_ids),
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
            .count()
        )
        # Currently in consultation
        in_consultation = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(all_queue_ids),
                QueueEntry.status == QueueEntryStatus.IN_CONSULTATION,
            )
            .count()
        )
        # Completed consultations today
        completed_consultations = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(all_queue_ids),
                QueueEntry.status == QueueEntryStatus.COMPLETED,
                QueueEntry.joined_at >= today_start,
            )
            .count()
        )
        # No shows today
        no_shows = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(all_queue_ids),
                QueueEntry.status == QueueEntryStatus.NO_SHOW,
                QueueEntry.joined_at >= today_start,
            )
            .count()
        )
        # Doctor delays recorded today
        doctor_delays = (
            db.query(QueueEvent)
            .filter(
                QueueEvent.queue_id.in_(all_queue_ids),
                QueueEvent.event_type == QueueEventType.DOCTOR_DELAY.value,
                QueueEvent.event_time >= today_start,
            )
            .count()
        )
        # Emergency events inserted today
        emergency_events = (
            db.query(QueueEvent)
            .filter(
                QueueEvent.queue_id.in_(all_queue_ids),
                QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value,
                QueueEvent.event_time >= today_start,
            )
            .count()
        )

    # Only return ACTIVE sessions with ACTIVE queues for the dashboard cards
    sessions = (
        db.query(OPDSession)
        .options(joinedload(OPDSession.queues))
        .filter(
            OPDSession.department_id.in_(dept_ids),
            OPDSession.status == SessionStatus.ACTIVE,
        )
        .all()
    ) if dept_ids else []

    queues_list = []
    for s in sessions:
        doc = doc_dict.get(s.doctor_id)
        dept = dept_dict.get(s.department_id)
        for q in s.queues:
            # Only include ACTIVE queues
            if q.status != QueueStatus.ACTIVE:
                continue

            waiting_cnt = (
                db.query(QueueEntry)
                .filter(QueueEntry.queue_id == q.id, QueueEntry.status == QueueEntryStatus.WAITING)
                .count()
            )
            booked_cnt = (
                db.query(QueueEntry)
                .filter(QueueEntry.queue_id == q.id, QueueEntry.status == QueueEntryStatus.BOOKED)
                .count()
            )

            # Determine current token and doctor status
            current_entry = (
                db.query(QueueEntry)
                .filter(
                    QueueEntry.queue_id == q.id,
                    QueueEntry.status.in_([QueueEntryStatus.IN_CONSULTATION, QueueEntryStatus.CALLED]),
                )
                .order_by(QueueEntry.status.desc())
                .first()
            )

            current_token = f"Q{current_entry.token_number:03d}" if current_entry else None
            if current_entry and current_entry.status == QueueEntryStatus.IN_CONSULTATION:
                queue_operational_status = "In Consultation"
            elif current_entry and current_entry.status == QueueEntryStatus.CALLED:
                queue_operational_status = "Calling"
            elif q.status == QueueStatus.PAUSED:
                queue_operational_status = "Paused"
            elif waiting_cnt > 0:
                queue_operational_status = "Available"
            else:
                queue_operational_status = "Available"

            from app.models.doctor_schedule import DoctorSchedule
            sched = db.query(DoctorSchedule).filter(
                DoctorSchedule.doctor_id == s.doctor_id,
                DoctorSchedule.schedule_date == q.queue_date,
            ).first()
            start_time_str = (
                sched.start_time.strftime("%H:%M")
                if sched and sched.start_time
                else (s.starts_at.strftime("%H:%M") if s.starts_at else "09:00")
            )
            end_time_str = (
                sched.end_time.strftime("%H:%M")
                if sched and sched.end_time
                else (s.ends_at.strftime("%H:%M") if s.ends_at else "13:00")
            )
            total_active = waiting_cnt + booked_cnt

            queues_list.append({
                "queue_id": str(q.id),
                "queue_name": q.name,
                "queue_date": q.queue_date.isoformat() if q.queue_date else None,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "status": q.status.value,
                "operational_status": queue_operational_status,
                "session_id": str(s.id),
                "department_id": str(s.department_id),
                "department_name": dept.name if dept else "General",
                "doctor_id": str(s.doctor_id),
                "doctor_name": doc.name if doc else "Doctor On Duty",
                "current_token": current_token,
                "waiting_count": total_active,
                "total_waiting": waiting_cnt,
                "total_booked": booked_cnt,
                "total_active": total_active,
            })

    return {
        "hospital": HospitalBrief.model_validate(hospital),
        "departments": [DepartmentBrief.model_validate(d) for d in departments],
        "doctors": [
            {
                "id": str(d.id),
                "name": d.name,
                "department_id": str(d.department_id),
                "department_name": dept_dict[d.department_id].name if d.department_id in dept_dict else "General",
                "status": d.status.value,
            }
            for d in doctors
        ],
        "queues": queues_list,
        "metrics": {
            "today_appointments": today_appointments,
            "active_queues": active_queues_count,
            "waiting_patients": waiting_patients,
            "in_consultation": in_consultation,
            "completed_consultations": completed_consultations,
            "no_shows": no_shows,
            "doctor_delays": doctor_delays,
            "emergency_events": emergency_events,
        },
    }
