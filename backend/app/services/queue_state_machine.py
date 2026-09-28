import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Set, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.services.queue_engine import QueueEngineService, format_token

logger = logging.getLogger(__name__)


# Authoritative state transition graph
VALID_TRANSITIONS: Dict[QueueEntryStatus, Set[QueueEntryStatus]] = {
    QueueEntryStatus.CREATED: {QueueEntryStatus.BOOKED, QueueEntryStatus.WAITING},
    QueueEntryStatus.BOOKED: {
        QueueEntryStatus.ARRIVED,
        QueueEntryStatus.WAITING,
        QueueEntryStatus.NO_SHOW,
    },
    QueueEntryStatus.ARRIVED: {
        QueueEntryStatus.WAITING,
        QueueEntryStatus.CALLED,
        QueueEntryStatus.NO_SHOW,
    },
    QueueEntryStatus.WAITING: {
        QueueEntryStatus.CALLED,
        QueueEntryStatus.TEMPORARILY_LEFT,
        QueueEntryStatus.NO_SHOW,
    },
    QueueEntryStatus.CALLED: {
        QueueEntryStatus.IN_CONSULTATION,
        QueueEntryStatus.NO_SHOW,
    },
    QueueEntryStatus.IN_CONSULTATION: {
        QueueEntryStatus.COMPLETED,
    },
    QueueEntryStatus.TEMPORARILY_LEFT: {
        QueueEntryStatus.RETURNED,
    },
    QueueEntryStatus.RETURNED: {
        QueueEntryStatus.WAITING,  # via STAFF_REQUEUES
    },
    QueueEntryStatus.COMPLETED: set(),
    QueueEntryStatus.NO_SHOW: set(),
}


class QueueStateMachineService:
    """Centralized service managing all QueueEntry state transitions and operational events."""

    @staticmethod
    def validate_transition(current_status: QueueEntryStatus, target_status: QueueEntryStatus) -> None:
        """Validate whether a state transition is permitted by the state machine.

        Raises:
            HTTPException: 409 Conflict if transition is not permitted.
        """
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Invalid state transition: Cannot transition entry from "
                    f"'{current_status.value}' to '{target_status.value}'. "
                    f"Allowed transitions: {[s.value for s in allowed]}"
                ),
            )

    @staticmethod
    def _dispatch_entry_update(
        db: Session,
        entry: QueueEntry,
        event_type: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Broadcast live queue entry state changes to patient, user, queue, and hospital WebSockets, and send in-app notifications."""
        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            from app.services.notifications.service import NotificationService
            from app.models.queue import Queue

            now_iso = datetime.now(timezone.utc).isoformat()

            # Resolve hospital_id
            hospital_id = None
            if entry.queue and entry.queue.opd_session and entry.queue.opd_session.department:
                hospital_id = entry.queue.opd_session.department.hospital_id
            elif entry.queue_id:
                q = db.query(Queue).filter(Queue.id == entry.queue_id).first()
                if q and q.opd_session and q.opd_session.department:
                    hospital_id = q.opd_session.department.hospital_id

            msg = {
                "type": "QUEUE_ENTRY_UPDATED",
                "version": 1,
                "timestamp": now_iso,
                "entry_id": str(entry.id),
                "queue_id": str(entry.queue_id),
                "status": entry.status.value if hasattr(entry.status, "value") else str(entry.status),
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "event_type": event_type,
                "payload": payload or {},
            }

            # 1. Send to patient entry socket
            safe_run_async(connection_manager.send_to_patient(entry.id, msg))
            # 2. Send to user socket (patient dashboard)
            if entry.patient_user_id:
                safe_run_async(connection_manager.send_to_user(entry.patient_user_id, msg))
            # 3. Broadcast to queue socket (staff queue control)
            safe_run_async(connection_manager.broadcast_to_queue(entry.queue_id, msg))
            # 4. Broadcast to hospital socket (staff operations center)
            if hospital_id:
                safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, msg))

            # 5. Create in-app notification on key milestones
            if entry.patient_user_id:
                notif_service = NotificationService()
                title = None
                msg_text = None
                tok = format_token(entry.token_number)
                if event_type == QueueEventType.PATIENT_ARRIVED.value:
                    title = "Arrival Recorded"
                    msg_text = f"Arrival confirmed for Token {tok}. You are now in line."
                elif event_type == QueueEventType.PATIENT_CALLED.value:
                    title = "Your Turn — Please Enter"
                    msg_text = f"Token {tok} has been called! Please proceed to the doctor's room."
                elif event_type == QueueEventType.CONSULTATION_STARTED.value:
                    title = "Consultation In Progress"
                    msg_text = f"Your consultation for Token {tok} has started."
                elif event_type == QueueEventType.CONSULTATION_COMPLETED.value:
                    title = "Consultation Completed"
                    msg_text = f"Your consultation for Token {tok} has concluded. Thank you."
                elif event_type == QueueEventType.PATIENT_NO_SHOW.value:
                    title = "Marked No-Show"
                    msg_text = f"Token {tok} was marked as a no-show."

                if title and msg_text:
                    notif_service.send_in_app_notification(
                        db=db,
                        user_id=entry.patient_user_id,
                        queue_entry_id=entry.id,
                        title=title,
                        message=msg_text,
                        notification_type=event_type,
                        payload=payload,
                    )
        except Exception as e:
            logger.warning("Error dispatching queue entry update: %s", e)


    @classmethod
    def mark_arrived(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Transition patient from BOOKED (or CREATED) to ARRIVED upon physical clinic arrival."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.ARRIVED)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.ARRIVED
        entry.arrived_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_ARRIVED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.ARRIVED.value,
                "arrived_at": now.isoformat(),
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_ARRIVED.value, event.payload_json)
        return entry, affected_ids

    @classmethod
    def mark_waiting(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Transition patient from ARRIVED (or BOOKED) to WAITING."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.WAITING)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.WAITING
        if not entry.arrived_at:
            entry.arrived_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_CHECKED_IN.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.WAITING.value,
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_CHECKED_IN.value, event.payload_json)
        return entry, affected_ids

    @classmethod
    def call_next_patient(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Determine and call the next eligible WAITING patient in priority and arrival order."""
        queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if queue.status != QueueStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot call next patient: Queue is currently {queue.status.value}",
            )

        ordered = QueueEngineService.get_ordered_waiting_entries(db, queue_id)
        if not ordered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No eligible waiting patients in this queue",
            )

        next_entry = ordered[0]
        cls.validate_transition(next_entry.status, QueueEntryStatus.CALLED)

        now = datetime.now(timezone.utc)
        prev_status = next_entry.status
        next_entry.status = QueueEntryStatus.CALLED
        next_entry.called_at = now

        # Append-only audit event
        event = QueueEvent(
            queue_id=queue_id,
            queue_entry_id=next_entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_CALLED.value,
            event_time=now,
            payload_json={
                "token_number": next_entry.token_number,
                "token_display": format_token(next_entry.token_number),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.CALLED.value,
                "action": "CALL_NEXT",
            },
        )
        db.add(event)

        # Identify downstream affected entries (all remaining waiting entries)
        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, queue_id, from_position=1)
        # Exclude called entry itself from downstream
        downstream_ids = [eid for eid in affected_ids if eid != next_entry.id]

        db.commit()
        db.refresh(next_entry)
        cls._dispatch_entry_update(db, next_entry, QueueEventType.PATIENT_CALLED.value, event.payload_json)
        return next_entry, downstream_ids

    @classmethod
    def call_patient(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Call a specific eligible patient in WAITING state."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.CALLED)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.CALLED
        entry.called_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_CALLED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.CALLED.value,
                "action": "CALL_SPECIFIC",
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)
        downstream_ids = [eid for eid in affected_ids if eid != entry.id]

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_CALLED.value, event.payload_json)
        return entry, downstream_ids

    @classmethod
    def start_consultation(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Consultation:
        """Transition patient from CALLED to IN_CONSULTATION and create consultation record (DEC-031)."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.IN_CONSULTATION)

        # Check if consultation row already exists (prevent double initialization)
        existing_consultation = db.query(Consultation).filter(Consultation.queue_entry_id == entry.id).first()
        if existing_consultation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Consultation already initiated for this entry",
            )

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.IN_CONSULTATION

        doctor_id = entry.queue.opd_session.doctor_id
        consultation = Consultation(
            queue_entry_id=entry.id,
            doctor_id=doctor_id,
            started_at=now,
        )
        db.add(consultation)

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.CONSULTATION_STARTED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "doctor_id": str(doctor_id),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.IN_CONSULTATION.value,
            },
        )
        db.add(event)

        db.commit()
        db.refresh(consultation)
        cls._dispatch_entry_update(db, entry, QueueEventType.CONSULTATION_STARTED.value, event.payload_json)
        return consultation

    @classmethod
    def complete_consultation(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
        interruption_notes: Optional[str] = None,
    ) -> Consultation:
        """Transition patient from IN_CONSULTATION to COMPLETED and record duration (DEC-031)."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.COMPLETED)

        consultation = (
            db.query(Consultation)
            .filter(Consultation.queue_entry_id == entry.id)
            .with_for_update()
            .first()
        )
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation record not found for this entry",
            )

        if consultation.completed_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Consultation has already been completed",
            )

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.COMPLETED

        consultation.completed_at = now
        s_time = consultation.started_at
        if s_time.tzinfo is None:
            s_time = s_time.replace(tzinfo=timezone.utc)
        duration = max(0, int((now - s_time).total_seconds()))
        consultation.duration_seconds = duration
        if interruption_notes:
            consultation.interruption_notes = interruption_notes

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.CONSULTATION_COMPLETED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "duration_seconds": duration,
                "interruption_notes": interruption_notes,
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.COMPLETED.value,
            },
        )
        db.add(event)

        db.commit()
        db.refresh(consultation)
        cls._dispatch_entry_update(db, entry, QueueEventType.CONSULTATION_COMPLETED.value, event.payload_json)

        # Trigger dynamic reforecast for downstream waiting patients
        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, entry.queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after complete_consultation: %s", err)

        return consultation

    @classmethod
    def mark_no_show(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Transition patient from WAITING or CALLED to NO_SHOW."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.NO_SHOW)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.NO_SHOW
        entry.no_show_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_NO_SHOW.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "reason": reason,
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.NO_SHOW.value,
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)
        downstream_ids = [eid for eid in affected_ids if eid != entry.id]

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_NO_SHOW.value, event.payload_json)

        # Trigger dynamic reforecast for remaining patients
        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, entry.queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after mark_no_show: %s", err)

        return entry, downstream_ids

    @classmethod
    def temporary_leave(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Transition patient from WAITING to TEMPORARILY_LEFT (DEC-033)."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.TEMPORARILY_LEFT)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.TEMPORARILY_LEFT
        entry.temporary_left_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_TEMPORARILY_LEFT.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "reason": reason,
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.TEMPORARILY_LEFT.value,
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)
        downstream_ids = [eid for eid in affected_ids if eid != entry.id]

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_TEMPORARILY_LEFT.value, event.payload_json)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, entry.queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after temporary_leave: %s", err)

        return entry, downstream_ids

    @classmethod
    def return_patient(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> QueueEntry:
        """Record patient return from TEMPORARILY_LEFT to RETURNED (DEC-033)."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.RETURNED)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.RETURNED
        entry.returned_at = now

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.PATIENT_RETURNED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.RETURNED.value,
            },
        )
        db.add(event)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.PATIENT_RETURNED.value, event.payload_json)
        return entry

    @classmethod
    def requeue_patient(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        actor_id: uuid.UUID,
        priority_class: Optional[PriorityClass] = None,
        reason: Optional[str] = None,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Staff-managed re-queueing of a RETURNED patient into WAITING state (DEC-033)."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        cls.validate_transition(entry.status, QueueEntryStatus.WAITING)

        now = datetime.now(timezone.utc)
        prev_status = entry.status
        entry.status = QueueEntryStatus.WAITING
        if priority_class:
            entry.priority_class = priority_class

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.STAFF_REQUEUES.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "priority_class": entry.priority_class.value,
                "reason": reason,
                "previous_status": prev_status.value,
                "new_status": QueueEntryStatus.WAITING.value,
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.STAFF_REQUEUES.value, event.payload_json)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, entry.queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after requeue_patient: %s", err)

        return entry, affected_ids

    @classmethod
    def change_priority(
        cls,
        db: Session,
        entry_id: uuid.UUID,
        new_priority: PriorityClass,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Change the priority rank of an active waiting patient."""
        entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).with_for_update().first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry with ID {entry_id} does not exist",
            )

        if entry.status != QueueEntryStatus.WAITING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot change priority: Entry status is '{entry.status.value}' (must be WAITING)",
            )

        old_priority = entry.priority_class
        if old_priority == new_priority:
            return entry, []

        entry.priority_class = new_priority
        now = datetime.now(timezone.utc)

        event_type = (
            QueueEventType.EMERGENCY_INSERTED.value
            if new_priority == PriorityClass.EMERGENCY
            else QueueEventType.PRIORITY_CHANGED.value
        )

        event = QueueEvent(
            queue_id=entry.queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=event_type,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "old_priority": old_priority.value,
                "new_priority": new_priority.value,
                "reason": reason,
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, entry.queue_id, from_position=1)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, event_type, event.payload_json)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, entry.queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after change_priority: %s", err)

        return entry, affected_ids

    @classmethod
    def insert_emergency(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        patient_user_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Tuple[QueueEntry, List[uuid.UUID]]:
        """Staff-controlled emergency insertion."""
        # Join patient with EMERGENCY priority
        entry = QueueEngineService.join_queue(
            db=db,
            queue_id=queue_id,
            patient_user_id=patient_user_id,
            priority_class=PriorityClass.EMERGENCY,
        )

        now = datetime.now(timezone.utc)
        # In-clinic emergency patients are physically present and waiting immediately
        entry.status = QueueEntryStatus.WAITING
        entry.arrived_at = now

        # Log specialized EMERGENCY_INSERTED event
        event = QueueEvent(
            queue_id=queue_id,
            queue_entry_id=entry.id,
            actor_user_id=actor_id,
            event_type=QueueEventType.EMERGENCY_INSERTED.value,
            event_time=now,
            payload_json={
                "token_number": entry.token_number,
                "token_display": format_token(entry.token_number),
                "priority_class": PriorityClass.EMERGENCY.value,
                "reason": reason,
                "action": "EMERGENCY_CREATION",
            },
        )
        db.add(event)

        affected_ids, _ = QueueEngineService.get_affected_downstream_entries(db, queue_id, from_position=1)

        db.commit()
        db.refresh(entry)
        cls._dispatch_entry_update(db, entry, QueueEventType.EMERGENCY_INSERTED.value, event.payload_json)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after insert_emergency: %s", err)

        return entry, affected_ids

    @classmethod
    def record_doctor_delay(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        delay_minutes: int,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> QueueEvent:
        """Record doctor delay operational disruption."""
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.DOCTOR_DELAY.value,
            event_time=now,
            payload_json={
                "delay_minutes": delay_minutes,
                "reason": reason,
            },
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Broadcast delay to queue and hospital
        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            delay_msg = {
                "type": "DOCTOR_DELAY",
                "queue_id": str(queue_id),
                "delay_minutes": delay_minutes,
                "reason": reason,
                "timestamp": now.isoformat(),
            }
            safe_run_async(connection_manager.broadcast_to_queue(queue_id, delay_msg))
            hospital_id = None
            if queue.opd_session and queue.opd_session.department:
                hospital_id = queue.opd_session.department.hospital_id
            if hospital_id:
                safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, delay_msg))
        except Exception as err:
            logger.warning("Failed to broadcast doctor delay: %s", err)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after doctor delay: %s", err)

        return event

    @classmethod
    def record_doctor_break_start(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        duration_minutes: int,
        actor_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> QueueEvent:
        """Record doctor break start event."""
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.DOCTOR_BREAK_STARTED.value,
            event_time=now,
            payload_json={
                "estimated_duration_minutes": duration_minutes,
                "reason": reason,
            },
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after doctor break start: %s", err)

        return event

    @classmethod
    def record_doctor_break_end(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> QueueEvent:
        """Record doctor break end event."""
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.DOCTOR_BREAK_ENDED.value,
            event_time=now,
            payload_json={},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        try:
            from app.services.reforecast_service import PredictionService
            PredictionService().reforecast_after_event(db, queue_id, event.id)
        except Exception as err:
            logger.warning("Reforecast failed after doctor break end: %s", err)

        return event

    @classmethod
    def pause_queue(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Queue:
        """Pause queue operations."""
        queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if queue.status == QueueStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Queue is already paused",
            )

        queue.status = QueueStatus.PAUSED
        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.QUEUE_PAUSED.value,
            event_time=now,
            payload_json={},
        )
        db.add(event)
        db.commit()
        db.refresh(queue)

        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            pause_msg = {
                "type": "QUEUE_PAUSED",
                "queue_id": str(queue_id),
                "timestamp": now.isoformat(),
            }
            safe_run_async(connection_manager.broadcast_to_queue(queue_id, pause_msg))
            hospital_id = None
            if queue.opd_session and queue.opd_session.department:
                hospital_id = queue.opd_session.department.hospital_id
            if hospital_id:
                safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, pause_msg))
        except Exception:
            pass

        return queue

    @classmethod
    def resume_queue(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Queue:
        """Resume paused queue operations."""
        queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if queue.status != QueueStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resume queue: Current status is '{queue.status.value}'",
            )

        queue.status = QueueStatus.ACTIVE
        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.QUEUE_RESUMED.value,
            event_time=now,
            payload_json={},
        )
        db.add(event)
        db.commit()
        db.refresh(queue)

        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            resume_msg = {
                "type": "QUEUE_RESUMED",
                "queue_id": str(queue_id),
                "timestamp": now.isoformat(),
            }
            safe_run_async(connection_manager.broadcast_to_queue(queue_id, resume_msg))
            hospital_id = None
            if queue.opd_session and queue.opd_session.department:
                hospital_id = queue.opd_session.department.hospital_id
            if hospital_id:
                safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, resume_msg))
        except Exception:
            pass

        return queue

    @classmethod
    def end_queue(
        cls,
        db: Session,
        queue_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Queue:
        """End and complete queue operations."""
        queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue with ID {queue_id} does not exist",
            )

        if queue.status == QueueStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Queue is already marked as completed.",
            )

        queue.status = QueueStatus.COMPLETED
        now = datetime.now(timezone.utc)
        event = QueueEvent(
            queue_id=queue_id,
            actor_user_id=actor_id,
            event_type=QueueEventType.QUEUE_CLOSED.value,
            event_time=now,
            payload_json={"ended_by_user_id": str(actor_id)},
        )
        db.add(event)
        db.commit()
        db.refresh(queue)

        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            end_msg = {
                "type": "QUEUE_COMPLETED",
                "queue_id": str(queue_id),
                "timestamp": now.isoformat(),
            }
            safe_run_async(connection_manager.broadcast_to_queue(queue_id, end_msg))
            hospital_id = None
            if queue.opd_session and queue.opd_session.department:
                hospital_id = queue.opd_session.department.hospital_id
            if hospital_id:
                safe_run_async(connection_manager.broadcast_to_hospital(hospital_id, end_msg))
        except Exception:
            pass

        return queue

