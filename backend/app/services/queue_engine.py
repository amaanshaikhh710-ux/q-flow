"""Queue engine service — authoritative position calculation, atomic token allocation, and snapshotting."""

import uuid
from datetime import date, datetime, timedelta, timezone, time as dt_time
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.doctor_availability import DoctorAvailability
from app.models.doctor_schedule import DoctorSchedule
from app.models.opd_session import OPDSession, SessionStatus
from app.models.consultation import Consultation
from app.schemas.queue import QueueEntryResponse


def format_token(token_number: int) -> str:
    """Format token integer into standard display token (e.g. Q001)."""
    return f"Q{token_number:03d}"


def get_priority_rank_expression():
    """SQL expression to rank priority classes: EMERGENCY (1) -> PRIORITY (2) -> NORMAL (3)."""
    return case(
        (QueueEntry.priority_class == PriorityClass.EMERGENCY, 1),
        (QueueEntry.priority_class == PriorityClass.PRIORITY, 2),
        else_=3,
    )


class QueueEngineService:
    """Core operational engine for Q-FLOW OPD queues."""

    @classmethod
    def resolve_date_specific_queue(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        target_date: date,
    ) -> Queue:
        """Return the authoritative queue for a doctor/date, creating it if needed."""
        if isinstance(queue_id, str):
            queue_id = uuid.UUID(queue_id)
        queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if target_date.year < 2000 or target_date.year > 2100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target_date '{target_date}'. Year must be between 2000 and 2100.",
            )

        if queue.queue_date == target_date:
            return queue

        session = queue.opd_session
        doctor_id = session.doctor_id if session else None
        if doctor_id:
            resolved = (
                db.query(Queue)
                .join(OPDSession, Queue.opd_session_id == OPDSession.id)
                .filter(
                    OPDSession.doctor_id == doctor_id,
                    Queue.queue_date == target_date,
                )
                .with_for_update()
                .first()
            )
            if resolved:
                return resolved

            schedule = (
                db.query(DoctorSchedule)
                .filter(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.schedule_date == target_date,
                )
                .first()
            )
            if schedule:
                session_match = (
                    db.query(OPDSession)
                    .filter(
                        OPDSession.doctor_id == doctor_id,
                        OPDSession.starts_at >= datetime.combine(target_date, dt_time.min).replace(tzinfo=timezone.utc),
                        OPDSession.starts_at < datetime.combine(target_date + timedelta(days=1), dt_time.min).replace(tzinfo=timezone.utc),
                    )
                    .with_for_update()
                    .first()
                )
                if not session_match:
                    session_match = OPDSession(
                        department_id=schedule.department_id,
                        doctor_id=doctor_id,
                        starts_at=datetime.combine(target_date, schedule.start_time).replace(tzinfo=timezone.utc),
                        ends_at=datetime.combine(target_date, schedule.end_time).replace(tzinfo=timezone.utc),
                        status=SessionStatus.ACTIVE,
                    )
                    db.add(session_match)
                    db.flush()

                new_queue = Queue(
                    opd_session_id=session_match.id,
                    name=f"Queue - {session_match.doctor.name if session_match.doctor else 'Doctor'}",
                    queue_date=target_date,
                    status=QueueStatus.ACTIVE,
                )
                db.add(new_queue)
                db.flush()
                return new_queue

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor has no scheduled clinic queue on {target_date.isoformat()} (this queue is for {queue.queue_date.isoformat()}). Booking rejected.",
        )

    @classmethod
    def get_ordered_waiting_entries(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        target_date: Optional[date] = None,
    ) -> List[QueueEntry]:
        """Return all WAITING and ARRIVED entries for a queue on a target date sorted by priority and arrival order."""
        rank_expr = get_priority_rank_expression()
        active_date = target_date or date.today()
        return (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id == queue_id,
                QueueEntry.appointment_date == active_date,
                QueueEntry.status.in_([QueueEntryStatus.WAITING, QueueEntryStatus.ARRIVED]),
            )
            .order_by(
                rank_expr.asc(),
                QueueEntry.joined_at.asc(),
                QueueEntry.token_number.asc(),
            )
            .all()
        )

    @classmethod
    def get_entry_position(cls, db: Session, entry: QueueEntry) -> Optional[int]:
        """Compute the server-authoritative 1-indexed waiting position for an entry."""
        if entry.status in (QueueEntryStatus.CALLED, QueueEntryStatus.IN_CONSULTATION):
            return 0

        if entry.status not in (QueueEntryStatus.WAITING, QueueEntryStatus.ARRIVED):
            return None

        ordered = cls.get_ordered_waiting_entries(db, entry.queue_id, target_date=entry.appointment_date)
        for idx, item in enumerate(ordered, start=1):
            if item.id == entry.id:
                return idx
        return None

    @classmethod
    def serialize_entry_response(cls, db: Session, entry: QueueEntry, position: Optional[int] = None) -> QueueEntryResponse:
        """Convert a QueueEntry model into an authoritative QueueEntryResponse schema."""
        if position is None:
            position = cls.get_entry_position(db, entry)

        patient_name = None
        patient_phone = None
        if entry.patient:
            patient_name = entry.patient.name
            patient_phone = entry.patient.phone
        elif entry.notes and "Patient: " in entry.notes:
            try:
                patient_name = entry.notes.split("Patient: ")[1].split("\n")[0].strip()
            except Exception:
                pass

        return QueueEntryResponse(
            id=entry.id,
            queue_id=entry.queue_id,
            patient_user_id=entry.patient_user_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            token_number=entry.token_number,
            token_display=format_token(entry.token_number),
            priority_class=entry.priority_class,
            status=entry.status,
            booking_source=getattr(entry, "booking_source", "ONLINE") or "ONLINE",
            notes=getattr(entry, "notes", None),
            position=position,
            appointment_date=entry.appointment_date,
            schedule_id=entry.schedule_id,
            appointment_time=entry.appointment_time,
            joined_at=entry.joined_at,
            arrived_at=entry.arrived_at,
            called_at=entry.called_at,
            temporary_left_at=entry.temporary_left_at,
            returned_at=entry.returned_at,
            no_show_at=entry.no_show_at,
            created_at=entry.created_at,
        )

    @classmethod
    def staff_book_appointment(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        patient_name: str,
        patient_phone: Optional[str] = None,
        booking_source: str = "STAFF",
        priority_class: PriorityClass = PriorityClass.NORMAL,
        appointment_date: Optional[date] = None,
        appointment_time: Optional[dt_time] = None,
        notes: Optional[str] = None,
    ) -> QueueEntry:
        """Staff booking operation (walk-in, phone, or reception desk)."""
        target_date = appointment_date or date.today()
        if target_date.year < 2000 or target_date.year > 2100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid appointment_date '{target_date}'. Year must be between 2000 and 2100.",
            )
        if target_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot book appointment for past date ({target_date.isoformat()})",
            )

        queue = cls.resolve_date_specific_queue(db, queue_id, target_date)

        if queue.status != QueueStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot book appointment: Queue is currently {queue.status.value}",
            )

        # Validate doctor schedule and availability on target_date
        if queue.opd_session and queue.opd_session.doctor_id:
            doc_id = queue.opd_session.doctor_id
            sched = (
                db.query(DoctorSchedule)
                .filter(
                    DoctorSchedule.doctor_id == doc_id,
                    DoctorSchedule.schedule_date == target_date,
                )
                .first()
            )
            # A date-specific staff schedule is the source of truth for every
            # booking, including same-day walk-ins. Availability overrides can
            # close a clinic but can never create one.
            if not sched:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor has no scheduled clinic on {target_date.isoformat()}. Booking rejected.",
                )
            if sched and sched.status not in ("AVAILABLE", "SCHEDULED"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor is marked unavailable/off-duty on {target_date.isoformat()}",
                )

            # Validate time window if appointment_time is provided
            if sched and appointment_time:
                if appointment_time < sched.start_time or appointment_time >= sched.end_time:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Requested appointment time {appointment_time.strftime('%H:%M')} is outside "
                            f"the doctor's scheduled shift ({sched.start_time.strftime('%H:%M')} – "
                            f"{sched.end_time.strftime('%H:%M')}). Booking rejected."
                        ),
                    )

            avail = (
                db.query(DoctorAvailability)
                .filter(
                    DoctorAvailability.doctor_id == doc_id,
                    DoctorAvailability.availability_date == target_date,
                )
                .first()
            )
            if avail and not avail.is_available:
                reason_msg = f": {avail.reason}" if avail.reason else ""
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor is marked unavailable on {target_date.isoformat()}{reason_msg}",
                )

            # If booking a future date, require an explicit schedule
            if target_date > date.today() and not sched and not avail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor has no scheduled clinic on {target_date.isoformat()}. Booking rejected.",
                )

        # Resolve or create Patient User
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        patient_user: Optional[User] = None
        clean_phone = patient_phone.strip() if patient_phone else None
        if clean_phone:
            patient_user = db.query(User).filter(User.phone == clean_phone).first()

        if not patient_user:
            dummy_hash = hash_password(uuid.uuid4().hex[:12])
            patient_user = User(
                name=patient_name.strip(),
                phone=clean_phone,
                email=None,
                password_hash=dummy_hash,
                role=UserRole.PATIENT,
            )
            db.add(patient_user)
            db.flush()

        target_queue_id = queue.id

        # Check for active existing ticket on target_date
        active_statuses = [
            QueueEntryStatus.BOOKED,
            QueueEntryStatus.ARRIVED,
            QueueEntryStatus.WAITING,
            QueueEntryStatus.CALLED,
            QueueEntryStatus.IN_CONSULTATION,
            QueueEntryStatus.TEMPORARILY_LEFT,
            QueueEntryStatus.RETURNED,
        ]
        # Collect all relevant queue IDs for this doctor and date to unify duplicate checking & tokens
        relevant_queue_ids = [target_queue_id]
        if queue.opd_session and queue.opd_session.doctor_id:
            try:
                other_qids = (
                    db.query(Queue.id)
                    .join(OPDSession, Queue.opd_session_id == OPDSession.id)
                    .filter(
                        OPDSession.doctor_id == queue.opd_session.doctor_id,
                        Queue.queue_date == target_date,
                    )
                    .all()
                )
                for (qid,) in other_qids:
                    if qid not in relevant_queue_ids:
                        relevant_queue_ids.append(qid)
            except Exception:
                pass

        existing_active = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.patient_user_id == patient_user.id,
                QueueEntry.appointment_date == target_date,
                QueueEntry.status.in_(active_statuses),
            )
            .first()
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Patient already has an active ticket (token {format_token(existing_active.token_number)}, "
                    f"status {existing_active.status.value}) on {target_date.isoformat()} in this queue"
                ),
            )

        # Compute next token number atomically scoped to target_date
        import time
        for attempt in range(5):
            try:
                max_token = (
                    db.query(func.coalesce(func.max(QueueEntry.token_number), 0))
                    .filter(
                        QueueEntry.queue_id.in_(relevant_queue_ids),
                        QueueEntry.appointment_date == target_date,
                    )
                    .scalar()
                )
                next_token = max_token + 1
                now = datetime.now(timezone.utc)

                # Patients joining today's active queue are WAITING
                # Future bookings are BOOKED
                initial_status = (
                    QueueEntryStatus.WAITING
                    if target_date == date.today()
                    else QueueEntryStatus.BOOKED
                )
                arrived_at = now if initial_status == QueueEntryStatus.WAITING else None

                entry = QueueEntry(
                    queue_id=target_queue_id,
                    patient_user_id=patient_user.id,
                    appointment_date=target_date,
                    schedule_id=sched.id,
                    appointment_time=appointment_time,
                    token_number=next_token,
                    priority_class=priority_class,
                    status=initial_status,
                    booking_source=booking_source,
                    notes=notes,
                    joined_at=now,
                    arrived_at=arrived_at,
                )
                db.add(entry)
                db.flush()

                event = QueueEvent(
                    queue_id=target_queue_id,
                    queue_entry_id=entry.id,
                    actor_user_id=staff_user_id,
                    event_type=(
                        QueueEventType.PATIENT_JOINED.value
                        if initial_status == QueueEntryStatus.WAITING
                        else QueueEventType.APPOINTMENT_BOOKED.value
                    ),
                    event_time=now,
                    payload_json={
                        "token_number": next_token,
                        "token_display": format_token(next_token),
                        "priority_class": priority_class.value,
                        "status": initial_status.value,
                        "patient_user_id": str(patient_user.id),
                        "appointment_date": target_date.isoformat(),
                        "booking_source": booking_source,
                        "booked_by_staff_id": str(staff_user_id),
                        "notes": notes,
                    },
                )
                db.add(event)
                db.commit()
                db.refresh(entry)
                return entry
            except IntegrityError as e:
                db.rollback()
                err_str = str(e).lower()
                if attempt < 4 and ("token_number" in err_str or "uq_queue" in err_str):
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise

    @classmethod
    def join_queue(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        patient_user_id: uuid.UUID,
        priority_class: PriorityClass = PriorityClass.NORMAL,
        appointment_date: Optional[date] = None,
        appointment_time: Optional[dt_time] = None,
    ) -> QueueEntry:
        """Atomically join a patient into a queue with row-level locking."""
        target_date = appointment_date or date.today()
        if target_date.year < 2000 or target_date.year > 2100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid appointment_date '{target_date}'. Year must be between 2000 and 2100.",
            )
        if target_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot book appointment for past date ({target_date.isoformat()})",
            )

        queue = cls.resolve_date_specific_queue(db, queue_id, target_date)

        if queue.status != QueueStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot join queue: Queue is currently {queue.status.value}",
            )

        # Validate doctor schedule and availability on target_date
        if queue.opd_session and queue.opd_session.doctor_id:
            doc_id = queue.opd_session.doctor_id
            sched = (
                db.query(DoctorSchedule)
                .filter(
                    DoctorSchedule.doctor_id == doc_id,
                    DoctorSchedule.schedule_date == target_date,
                )
                .first()
            )
            # Same strict schedule authority as staff-created appointments.
            if not sched:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor has no scheduled clinic on {target_date.isoformat()}. Booking rejected.",
                )
            if sched and sched.status not in ("AVAILABLE", "SCHEDULED"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor is marked unavailable/off-duty on {target_date.isoformat()}",
                )

            # Validate time window if appointment_time is provided
            if sched and appointment_time:
                if appointment_time < sched.start_time or appointment_time >= sched.end_time:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Requested appointment time {appointment_time.strftime('%H:%M')} is outside "
                            f"the doctor's scheduled shift ({sched.start_time.strftime('%H:%M')} – "
                            f"{sched.end_time.strftime('%H:%M')}). Booking rejected."
                        ),
                    )

            avail = (
                db.query(DoctorAvailability)
                .filter(
                    DoctorAvailability.doctor_id == doc_id,
                    DoctorAvailability.availability_date == target_date,
                )
                .first()
            )
            if avail and not avail.is_available:
                reason_msg = f": {avail.reason}" if avail.reason else ""
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor is marked unavailable on {target_date.isoformat()}{reason_msg}",
                )

            # If booking a future date, require an explicit schedule
            if target_date > date.today() and not sched and not avail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor has no scheduled clinic on {target_date.isoformat()}. Booking rejected.",
                )

        target_queue_id = queue.id

        # Check for active existing ticket on target_date
        active_statuses = [
            QueueEntryStatus.BOOKED,
            QueueEntryStatus.ARRIVED,
            QueueEntryStatus.WAITING,
            QueueEntryStatus.CALLED,
            QueueEntryStatus.IN_CONSULTATION,
            QueueEntryStatus.TEMPORARILY_LEFT,
            QueueEntryStatus.RETURNED,
        ]
        # Collect all relevant queue IDs for this doctor and date to unify duplicate checking & tokens
        relevant_queue_ids = [target_queue_id]
        if queue.opd_session and queue.opd_session.doctor_id:
            try:
                other_qids = (
                    db.query(Queue.id)
                    .join(OPDSession, Queue.opd_session_id == OPDSession.id)
                    .filter(
                        OPDSession.doctor_id == queue.opd_session.doctor_id,
                        Queue.queue_date == target_date,
                    )
                    .all()
                )
                for (qid,) in other_qids:
                    if qid not in relevant_queue_ids:
                        relevant_queue_ids.append(qid)
            except Exception:
                pass

        existing_active = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.patient_user_id == patient_user_id,
                QueueEntry.appointment_date == target_date,
                QueueEntry.status.in_(active_statuses),
            )
            .first()
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Patient already has an active ticket (token {format_token(existing_active.token_number)}, "
                    f"status {existing_active.status.value}) on {target_date.isoformat()} in this queue"
                ),
            )

        # Compute next token number atomically with optimistic retry
        import time
        for attempt in range(5):
            try:
                max_token = (
                    db.query(func.coalesce(func.max(QueueEntry.token_number), 0))
                    .filter(
                        QueueEntry.queue_id.in_(relevant_queue_ids),
                        QueueEntry.appointment_date == target_date,
                    )
                    .scalar()
                )
                next_token = max_token + 1
                now = datetime.now(timezone.utc)

                initial_status = (
                    QueueEntryStatus.BOOKED
                    if appointment_time is not None or target_date > date.today()
                    else QueueEntryStatus.WAITING
                )
                arrived_at = now if initial_status == QueueEntryStatus.WAITING else None

                entry = QueueEntry(
                    queue_id=target_queue_id,
                    patient_user_id=patient_user_id,
                    appointment_date=target_date,
                    schedule_id=sched.id,
                    appointment_time=appointment_time,
                    token_number=next_token,
                    priority_class=priority_class,
                    status=initial_status,
                    booking_source="ONLINE",
                    joined_at=now,
                    arrived_at=arrived_at,
                )
                db.add(entry)
                db.flush()

                event = QueueEvent(
                    queue_id=target_queue_id,
                    queue_entry_id=entry.id,
                    actor_user_id=patient_user_id,
                    event_type=(
                        QueueEventType.PATIENT_JOINED.value
                        if initial_status == QueueEntryStatus.WAITING
                        else QueueEventType.APPOINTMENT_BOOKED.value
                    ),
                    event_time=now,
                    payload_json={
                        "token_number": next_token,
                        "token_display": format_token(next_token),
                        "priority_class": priority_class.value,
                        "status": initial_status.value,
                        "patient_user_id": str(patient_user_id),
                        "appointment_date": target_date.isoformat(),
                        "booking_source": "ONLINE",
                    },
                )
                db.add(event)
                db.commit()
                db.refresh(entry)
                return entry
            except IntegrityError as e:
                db.rollback()
                err_str = str(e).lower()
                if attempt < 4 and ("token_number" in err_str or "uq_queue" in err_str):
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise

    @classmethod
    def get_affected_downstream_entries(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        from_position: int = 1,
        target_date: Optional[date] = None,
    ) -> Tuple[List[uuid.UUID], List[QueueEntryResponse]]:
        """Identify active waiting entries whose queue position is impacted by a mutation."""
        waiting_entries = cls.get_ordered_waiting_entries(db, queue_id, target_date=target_date)
        affected_entries = []
        affected_ids = []

        for idx, item in enumerate(waiting_entries, start=1):
            if idx >= from_position:
                resp = cls.serialize_entry_response(db, item, position=idx)
                affected_entries.append(resp)
                affected_ids.append(item.id)

        return affected_ids, affected_entries

    @classmethod
    def get_queue_snapshot(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Compute the authoritative snapshot of the queue for a specific operational date (defaults to today)."""
        if isinstance(queue_id, str):
            queue_id = uuid.UUID(queue_id)
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if target_date and (target_date.year < 2000 or target_date.year > 2100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target_date '{target_date}'. Year must be between 2000 and 2100.",
            )

        active_date = target_date or queue.queue_date or date.today()

        # If target_date is specified and differs from this queue's queue_date,
        # resolve to the authoritative date-specific queue for this doctor/date.
        if target_date and queue.queue_date != target_date:
            try:
                date_specific_queue = cls.resolve_date_specific_queue(db, queue.id, target_date)
                if date_specific_queue:
                    queue = date_specific_queue
                    queue_id = queue.id
            except Exception:
                pass

        # Session and clinical info
        opd_session = queue.opd_session
        doctor_id = opd_session.doctor_id if opd_session else None
        doctor_name = opd_session.doctor.name if opd_session and opd_session.doctor else None
        dept_name = opd_session.department.name if opd_session and opd_session.department else None

        # Collect all relevant queue IDs for this doctor session on active_date
        relevant_queue_ids = [queue.id]
        if doctor_id:
            try:
                other_qids = (
                    db.query(Queue.id)
                    .join(OPDSession, Queue.opd_session_id == OPDSession.id)
                    .filter(OPDSession.doctor_id == doctor_id, Queue.queue_date == active_date)
                    .all()
                )
                for (qid,) in other_qids:
                    if qid not in relevant_queue_ids:
                        relevant_queue_ids.append(qid)
            except Exception:
                pass

        # Look up doctor schedule for active_date to preserve shift start and end times
        sched = None
        if doctor_id:
            sched = (
                db.query(DoctorSchedule)
                .filter(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.schedule_date == active_date,
                )
                .first()
            )

        def _dt_to_ist_time_str(dt_val, fallback: str) -> str:
            if not dt_val:
                return fallback
            dt_utc = dt_val if dt_val.tzinfo else dt_val.replace(tzinfo=timezone.utc)
            return dt_utc.astimezone(IST).strftime("%H:%M")

        start_time_str = (
            sched.start_time.strftime("%H:%M")
            if sched and sched.start_time
            else _dt_to_ist_time_str(opd_session.starts_at if opd_session else None, "09:00")
        )
        end_time_str = (
            sched.end_time.strftime("%H:%M")
            if sched and sched.end_time
            else _dt_to_ist_time_str(opd_session.ends_at if opd_session else None, "13:00")
        )

        hosp_id = None
        hosp_name = None
        if opd_session and opd_session.department and opd_session.department.hospital:
            hosp_id = opd_session.department.hospital.id
            hosp_name = opd_session.department.hospital.name

        # Active serving entry (today / active_date)
        serving_entry = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status == QueueEntryStatus.IN_CONSULTATION,
            )
            .first()
        )
        currently_serving = (
            cls.serialize_entry_response(db, serving_entry, position=0)
            if serving_entry
            else None
        )

        # Active called entry
        called_entry = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status == QueueEntryStatus.CALLED,
            )
            .first()
        )
        currently_called = (
            cls.serialize_entry_response(db, called_entry, position=0)
            if called_entry
            else None
        )

        # Ordered waiting list (physically arrived and waiting on active_date)
        rank_expr = get_priority_rank_expression()
        ordered_waiting = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status.in_([QueueEntryStatus.WAITING, QueueEntryStatus.ARRIVED]),
            )
            .order_by(
                rank_expr.asc(),
                QueueEntry.joined_at.asc(),
                QueueEntry.token_number.asc(),
            )
            .all()
        )
        waiting_serialized: List[QueueEntryResponse] = []
        for idx, item in enumerate(ordered_waiting, start=1):
            waiting_serialized.append(cls.serialize_entry_response(db, item, position=idx))

        next_patient = waiting_serialized[0] if waiting_serialized else None

        # Booked entries for active_date
        booked_entries_db = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status == QueueEntryStatus.BOOKED,
            )
            .order_by(QueueEntry.token_number.asc())
            .all()
        )
        booked_serialized = [cls.serialize_entry_response(db, item) for item in booked_entries_db]

        # Counts
        total_waiting = len(ordered_waiting)
        total_booked = len(booked_entries_db)
        total_in_consultation = 1 if serving_entry else 0
        total_active = total_waiting + total_booked + total_in_consultation
        total_completed = (
            db.query(func.count(QueueEntry.id))
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status == QueueEntryStatus.COMPLETED,
            )
            .scalar()
            or 0
        )
        total_no_show = (
            db.query(func.count(QueueEntry.id))
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.status == QueueEntryStatus.NO_SHOW,
            )
            .scalar()
            or 0
        )

        # Real average consultation duration from completed consultations (>= 60s)
        avg_consult_duration_sec: Optional[int] = None
        if doctor_id:
            completed_durations = (
                db.query(Consultation.duration_seconds)
                .join(QueueEntry, Consultation.queue_entry_id == QueueEntry.id)
                .filter(
                    QueueEntry.queue_id.in_(relevant_queue_ids),
                    QueueEntry.appointment_date == active_date,
                    Consultation.duration_seconds.isnot(None),
                    Consultation.duration_seconds >= 60,
                )
                .all()
            )
            durations_list = [d[0] for d in completed_durations if d[0] is not None and d[0] >= 60]
            if durations_list:
                avg_consult_duration_sec = int(sum(durations_list) / len(durations_list))
            else:
                # Fallback hierarchy: Doctor recent completed consultations across sessions (last 30 days)
                recent_completed = (
                    db.query(Consultation.duration_seconds)
                    .filter(
                        Consultation.doctor_id == doctor_id,
                        Consultation.duration_seconds.isnot(None),
                        Consultation.duration_seconds >= 60,
                    )
                    .order_by(Consultation.completed_at.desc())
                    .limit(20)
                    .all()
                )
                recent_list = [d[0] for d in recent_completed if d[0] is not None and d[0] >= 60]
                if recent_list:
                    avg_consult_duration_sec = int(sum(recent_list) / len(recent_list))

        # Real average waiting time from called/completed queue entries
        # waiting_time = actual consultation start or call timestamp - actual arrival timestamp
        avg_waiting_time_sec: Optional[int] = None
        called_entries = (
            db.query(QueueEntry)
            .filter(
                QueueEntry.queue_id.in_(relevant_queue_ids),
                QueueEntry.appointment_date == active_date,
                QueueEntry.called_at.isnot(None),
            )
            .all()
        )
        wait_durations: List[float] = []
        for e in called_entries:
            c_at = e.called_at if e.called_at.tzinfo else e.called_at.replace(tzinfo=timezone.utc)
            # Use arrived_at if recorded, or joined_at only if walk-in (arrived physically)
            arrival_ts = e.arrived_at or (e.joined_at if e.booking_source == "WALK_IN" else None)
            if arrival_ts:
                a_at = arrival_ts if arrival_ts.tzinfo else arrival_ts.replace(tzinfo=timezone.utc)
                if c_at >= a_at:
                    sec = (c_at - a_at).total_seconds()
                    if sec >= 60:
                        wait_durations.append(sec)
        if wait_durations:
            avg_waiting_time_sec = int(sum(wait_durations) / len(wait_durations))
        elif avg_consult_duration_sec is not None:
            # Fallback to historical completed consultations with arrival records for doctor
            historical_entries = (
                db.query(QueueEntry)
                .join(Consultation, QueueEntry.id == Consultation.queue_entry_id)
                .filter(
                    Consultation.doctor_id == doctor_id,
                    QueueEntry.called_at.isnot(None),
                    QueueEntry.arrived_at.isnot(None),
                )
                .order_by(Consultation.completed_at.desc())
                .limit(20)
                .all()
            )
            hist_waits = []
            for he in historical_entries:
                hc_at = he.called_at if he.called_at.tzinfo else he.called_at.replace(tzinfo=timezone.utc)
                ha_at = he.arrived_at if he.arrived_at.tzinfo else he.arrived_at.replace(tzinfo=timezone.utc)
                if hc_at >= ha_at:
                    sec = (hc_at - ha_at).total_seconds()
                    if sec >= 60:
                        hist_waits.append(sec)
            if hist_waits:
                avg_waiting_time_sec = int(sum(hist_waits) / len(hist_waits))

        # Real current consultation elapsed time
        current_consultation_elapsed_sec: Optional[int] = None
        if serving_entry:
            active_consultation = (
                db.query(Consultation)
                .filter(
                    Consultation.queue_entry_id == serving_entry.id,
                    Consultation.completed_at.is_(None),
                )
                .first()
            )
            now_utc = datetime.now(timezone.utc)
            if active_consultation and active_consultation.started_at:
                st = active_consultation.started_at
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
                current_consultation_elapsed_sec = max(0, int((now_utc - st).total_seconds()))
            elif serving_entry.called_at:
                ct = serving_entry.called_at
                if ct.tzinfo is None:
                    ct = ct.replace(tzinfo=timezone.utc)
                current_consultation_elapsed_sec = max(0, int((now_utc - ct).total_seconds()))

        # Real doctor delay impact
        delay_events = (
            db.query(QueueEvent)
            .filter(
                QueueEvent.queue_id.in_(relevant_queue_ids),
                QueueEvent.event_type == QueueEventType.DOCTOR_DELAY.value,
            )
            .all()
        )
        total_delay_min = 0
        for de in delay_events:
            if isinstance(de.payload_json, dict):
                total_delay_min += int(de.payload_json.get("delay_minutes", 0))

        # Real estimated remaining queue time (strictly based on actual consultation pace if available)
        estimated_remaining_queue_min: Optional[int] = None
        remaining_patients = total_waiting + total_booked + (1 if called_entry else 0)
        if remaining_patients == 0 and not serving_entry:
            estimated_remaining_queue_min = 0
        elif avg_consult_duration_sec is not None:
            workload_seconds = remaining_patients * avg_consult_duration_sec
            if serving_entry and current_consultation_elapsed_sec is not None:
                remaining_active = max(0, avg_consult_duration_sec - current_consultation_elapsed_sec)
                workload_seconds += remaining_active
            estimated_remaining_queue_min = max(1, int(round((workload_seconds + (total_delay_min * 60)) / 60)))

        return {
            "queue_id": queue.id,
            "queue_name": queue.name,
            "queue_date": active_date.isoformat() if active_date is not None else None,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "hospital_id": hosp_id,
            "hospital_name": hosp_name,
            "status": queue.status,
            "opd_session_id": queue.opd_session_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "department_name": dept_name,
            "currently_serving": currently_serving,
            "currently_called": currently_called,
            "next_patient": next_patient,
            "total_waiting": total_waiting,
            "total_booked": total_booked,
            "total_active": total_active,
            "total_in_consultation": total_in_consultation,
            "total_completed": total_completed,
            "total_no_show": total_no_show,
            "waiting_entries": waiting_serialized,
            "booked_entries": booked_serialized,
            "avg_consultation_duration_seconds": avg_consult_duration_sec,
            "avg_waiting_time_seconds": avg_waiting_time_sec,
            "current_consultation_elapsed_seconds": current_consultation_elapsed_sec,
            "delay_impact_minutes": total_delay_min,
            "estimated_remaining_queue_time_minutes": estimated_remaining_queue_min,
        }
