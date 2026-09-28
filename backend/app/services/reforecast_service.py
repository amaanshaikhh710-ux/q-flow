"""Dynamic Reforecast Service — uncertainty windows, start time calculation, explainability, and disruption propagation."""

import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

logger = logging.getLogger(__name__)

from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.services.prediction_engine import (
    RobustMedianPredictor,
    PredictionFeatureBuilder,
    BaseDurationPredictor,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
)
from app.services.hybrid_prediction_service import HybridPredictionService
from app.services.prediction_features import PredictionFeatureExtractor
from app.services.queue_engine import QueueEngineService, format_token

# Decision threshold: 10 minutes for meaningful patient ETA shifts
MEANINGFUL_CHANGE_THRESHOLD_MINUTES = 10

# Events that can change downstream waiting sequence or start times
REFORECAST_TRIGGERS = {
    QueueEventType.EMERGENCY_INSERTED.value,
    QueueEventType.PRIORITY_CHANGED.value,
    QueueEventType.PATIENT_NO_SHOW.value,
    QueueEventType.PATIENT_TEMPORARILY_LEFT.value,
    QueueEventType.PATIENT_RETURNED.value,
    QueueEventType.STAFF_REQUEUES.value,
    QueueEventType.CONSULTATION_STARTED.value,
    QueueEventType.CONSULTATION_COMPLETED.value,
    QueueEventType.DOCTOR_DELAY.value,
    QueueEventType.DOCTOR_BREAK_STARTED.value,
    QueueEventType.DOCTOR_BREAK_ENDED.value,
}


def build_explanation(
    event_type: str,
    shift_minutes: int,
    is_meaningful: bool,
    payload: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Generate deterministic, human-readable reason text and structured explanation payload."""
    abs_shift = abs(shift_minutes)
    reason_code = event_type

    if event_type == QueueEventType.EMERGENCY_INSERTED.value:
        text = f"Your estimated window moved {abs_shift} minutes later because an emergency patient was inserted ahead of you."
    elif event_type == QueueEventType.PRIORITY_CHANGED.value:
        if shift_minutes > 0:
            text = f"Your estimated window moved {abs_shift} minutes later because a priority patient was placed ahead of you."
        else:
            text = f"Your estimated window moved {abs_shift} minutes earlier following a queue priority adjustment."
    elif event_type == QueueEventType.PATIENT_NO_SHOW.value:
        text = f"Your estimated window moved {abs_shift} minutes earlier because a patient ahead of you was marked as a no-show."
    elif event_type == QueueEventType.PATIENT_TEMPORARILY_LEFT.value:
        text = f"Your estimated window moved {abs_shift} minutes earlier because a patient ahead temporarily stepped away."
    elif event_type == QueueEventType.STAFF_REQUEUES.value:
        text = f"Your estimated window updated following the re-queueing of a returning patient ahead of you."
    elif event_type == QueueEventType.DOCTOR_DELAY.value:
        text = f"Your estimated window moved {abs_shift} minutes later because the doctor reported an operational delay."
    elif event_type == QueueEventType.DOCTOR_BREAK_STARTED.value:
        text = f"Your estimated window moved {abs_shift} minutes later because the doctor is on a scheduled break."
    elif event_type == QueueEventType.DOCTOR_BREAK_ENDED.value:
        text = f"Your estimated window updated as the doctor concluded their break."
    elif event_type == QueueEventType.CONSULTATION_COMPLETED.value:
        text = f"Your estimated window updated following the completion of a consultation ahead of you."
    elif event_type == QueueEventType.PATIENT_JOINED.value:
        text = "Initial estimate based on current queue position and recent consultation durations."
    else:
        text = f"Your estimated window updated following live queue recalculation ({event_type})."

    explanation_json = {
        "trigger": event_type,
        "reason_code": reason_code,
        "shift_minutes": shift_minutes,
        "is_meaningful_change": is_meaningful,
        "metadata": payload,
    }
    return text, explanation_json


IST = timezone(timedelta(hours=5, minutes=30))


class PredictionService:
    """Service managing start-time calculations, uncertainty windows, snapshots, and reforecasting."""

    def __init__(self, predictor: Optional[BaseDurationPredictor] = None):
        self.predictor = predictor or HybridPredictionService()

    def calculate_entry_prediction(
        self,
        db: Session,
        entry: QueueEntry,
    ) -> Dict[str, Any]:
        """Compute estimated start, duration, and uncertainty window for a specific entry.
        
        MANDATORY RULE:
        The predicted consultation time is strictly anchored inside the authoritative OPD session
        (e.g. 10:00 AM – 12:00 PM). It never drifts outside the clinic shift or uses current-time
        offset for future/scheduled appointments.
        """
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(IST)

        queue = entry.queue
        opd_session = queue.opd_session if queue else None
        doctor_id = opd_session.doctor_id if opd_session else None
        dept_id = opd_session.department_id if opd_session else None

        # 1. Fetch historical durations for duration prediction
        history, tier_label = PredictionFeatureBuilder.get_historical_durations(db, doctor_id, dept_id)
        features = PredictionFeatureBuilder.build_entry_features(db, entry, patients_ahead=0)

        # 2. Enrich with ML inference features (zero leakage)
        ml_features = PredictionFeatureExtractor.extract_inference_features(
            db=db,
            entry=entry,
            patients_ahead_count=0,
            reference_time=now_utc,
        )
        features.update(ml_features)

        pred_duration_sec, unc_min, model_type, model_version, status = self.predictor.predict_duration(
            features=features,
            historical_durations=history,
        )

        # 3. If already in consultation, expected start was actual started_at
        if entry.status == QueueEntryStatus.IN_CONSULTATION:
            consultation = db.query(Consultation).filter(Consultation.queue_entry_id == entry.id).first()
            start_at = consultation.started_at if consultation else now_utc
            end_at = start_at + timedelta(seconds=pred_duration_sec) + timedelta(minutes=unc_min)
            return {
                "predicted_start_at": start_at,
                "predicted_end_at": end_at,
                "predicted_duration_seconds": pred_duration_sec,
                "uncertainty_minutes": unc_min,
                "model_type": model_type,
                "model_version": model_version,
                "prediction_status": status,
                "features": features,
            }

        # 4. If CALLED, standing at door; expected start is now
        if entry.status == QueueEntryStatus.CALLED:
            start_at = now_utc
            end_at = start_at + timedelta(seconds=pred_duration_sec) + timedelta(minutes=unc_min)
            return {
                "predicted_start_at": start_at,
                "predicted_end_at": end_at,
                "predicted_duration_seconds": pred_duration_sec,
                "uncertainty_minutes": unc_min,
                "model_type": model_type,
                "model_version": model_version,
                "prediction_status": status,
                "features": features,
            }

        # 5. Resolve the authoritative scheduled date & time window for this OPD session
        target_date = entry.appointment_date or (queue.queue_date if queue else None) or now_ist.date()

        from app.models.doctor_schedule import DoctorSchedule
        sched = None
        if entry.schedule_id:
            sched = db.query(DoctorSchedule).filter(DoctorSchedule.id == entry.schedule_id).first()
        if not sched and doctor_id:
            sched = (
                db.query(DoctorSchedule)
                .filter(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.schedule_date == target_date,
                )
                .first()
            )

        from datetime import time as dt_time
        if sched and sched.start_time and sched.end_time:
            session_start_time = sched.start_time
            session_end_time = sched.end_time
        elif opd_session and opd_session.starts_at and opd_session.ends_at:
            s_at = opd_session.starts_at if opd_session.starts_at.tzinfo else opd_session.starts_at.replace(tzinfo=timezone.utc)
            e_at = opd_session.ends_at if opd_session.ends_at.tzinfo else opd_session.ends_at.replace(tzinfo=timezone.utc)
            session_start_time = s_at.astimezone(IST).time()
            session_end_time = e_at.astimezone(IST).time()
        else:
            session_start_time = dt_time(10, 0)
            session_end_time = dt_time(12, 0)

        session_start_dt_ist = datetime.combine(target_date, session_start_time, tzinfo=IST)
        session_end_dt_ist = datetime.combine(target_date, session_end_time, tzinfo=IST)

        # 6. Check for active doctor delay reported for this queue session
        delay_seconds = 0
        latest_delay_event = (
            db.query(QueueEvent)
            .filter(
                QueueEvent.queue_id == entry.queue_id,
                QueueEvent.event_type == QueueEventType.DOCTOR_DELAY.value,
            )
            .order_by(QueueEvent.event_time.desc())
            .first()
        )
        if latest_delay_event:
            delay_mins = latest_delay_event.payload_json.get("delay_minutes", 0)
            delay_seconds = delay_mins * 60

        # Check for active doctor break
        break_remaining_seconds = 0
        latest_break_start = (
            db.query(QueueEvent)
            .filter(
                QueueEvent.queue_id == entry.queue_id,
                QueueEvent.event_type == QueueEventType.DOCTOR_BREAK_STARTED.value,
            )
            .order_by(QueueEvent.event_time.desc())
            .first()
        )
        if latest_break_start:
            latest_break_end = (
                db.query(QueueEvent)
                .filter(
                    QueueEvent.queue_id == entry.queue_id,
                    QueueEvent.event_type == QueueEventType.DOCTOR_BREAK_ENDED.value,
                    QueueEvent.event_time > latest_break_start.event_time,
                )
                .first()
            )
            if not latest_break_end:
                break_duration_mins = latest_break_start.payload_json.get("estimated_duration_minutes", 15)
                b_time = latest_break_start.event_time
                if b_time.tzinfo is None:
                    b_time = b_time.replace(tzinfo=timezone.utc)
                break_elapsed = max(0, int((now_utc - b_time).total_seconds()))
                break_remaining_seconds = max(60, (break_duration_mins * 60) - break_elapsed)

        # 7. Determine if clinic session is live today or scheduled in future
        # A clinic session is actively live if it is today AND the queue status is ACTIVE or PAUSED
        is_queue_open = bool(queue and queue.status in (QueueStatus.ACTIVE, "ACTIVE", "active", QueueStatus.PAUSED, "PAUSED", "paused"))
        is_live_today = (target_date == now_ist.date()) and is_queue_open

        if is_live_today:
            # Active ongoing clinic session: baseline is current operational time
            accumulated_seconds = 0

            # A. Currently serving consultation
            active_consult = (
                db.query(Consultation)
                .join(QueueEntry, Consultation.queue_entry_id == QueueEntry.id)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    QueueEntry.status == QueueEntryStatus.IN_CONSULTATION,
                    Consultation.completed_at.is_(None),
                )
                .first()
            )
            if active_consult:
                s_at = active_consult.started_at
                if s_at.tzinfo is None:
                    s_at = s_at.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((now_utc - s_at).total_seconds()))
                if elapsed < pred_duration_sec:
                    remaining_active = pred_duration_sec - elapsed
                else:
                    dynamic_tail = max(300, min(900, int(pred_duration_sec * 0.35)))
                    remaining_active = dynamic_tail
                accumulated_seconds += remaining_active

            # B. Currently called patient
            called_entry = (
                db.query(QueueEntry)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    QueueEntry.status == QueueEntryStatus.CALLED,
                )
                .first()
            )
            if called_entry:
                accumulated_seconds += pred_duration_sec

            # C. Waiting/arrived patients ahead in live line
            ordered_waiting = QueueEngineService.get_ordered_waiting_entries(db, entry.queue_id, target_date=target_date)
            patients_ahead_count = 0
            for item in ordered_waiting:
                if item.id == entry.id:
                    break
                patients_ahead_count += 1
                accumulated_seconds += pred_duration_sec
            features["patients_ahead"] = patients_ahead_count

            accumulated_seconds += delay_seconds + break_remaining_seconds
            if active_consult or called_entry or now_ist >= session_start_dt_ist:
                predicted_start_ist = now_ist + timedelta(seconds=accumulated_seconds)
            else:
                predicted_start_ist = session_start_dt_ist + timedelta(seconds=accumulated_seconds)

            if entry.appointment_time:
                slot_start_ist = datetime.combine(target_date, entry.appointment_time, tzinfo=IST) + timedelta(seconds=delay_seconds)
                predicted_start_ist = max(slot_start_ist, predicted_start_ist)
        else:
            # Scheduled future appointment or pre-clinic: strictly anchored to OPD session!
            # Count entries booked/waiting ahead in this session for target_date
            entries_ahead_count = (
                db.query(QueueEntry)
                .filter(
                    QueueEntry.queue_id == entry.queue_id,
                    QueueEntry.appointment_date == target_date,
                    QueueEntry.status.in_([
                        QueueEntryStatus.BOOKED,
                        QueueEntryStatus.WAITING,
                        QueueEntryStatus.ARRIVED,
                    ]),
                    QueueEntry.token_number < entry.token_number,
                )
                .count()
            )
            features["patients_ahead"] = entries_ahead_count
            progression_seconds = entries_ahead_count * pred_duration_sec

            if entry.appointment_time:
                slot_start_ist = datetime.combine(target_date, entry.appointment_time, tzinfo=IST)
                # Anchored to their booked appointment slot, but if queue progression takes longer, honors queue
                predicted_start_ist = max(slot_start_ist, session_start_dt_ist + timedelta(seconds=progression_seconds))
            else:
                predicted_start_ist = session_start_dt_ist + timedelta(seconds=progression_seconds)

            predicted_start_ist += timedelta(seconds=delay_seconds)

        # 8. Clinical Session Bounds Enforcement:
        # Never allow predicted consultation to start before session start unless an active consultation is already underway
        if not (is_live_today and (active_consult or called_entry)) and predicted_start_ist < session_start_dt_ist:
            predicted_start_ist = session_start_dt_ist

        predicted_end_ist = (
            predicted_start_ist
            + timedelta(seconds=pred_duration_sec)
            + timedelta(minutes=unc_min)
        )

        # Convert to UTC for authoritative database storage
        predicted_start_at = predicted_start_ist.astimezone(timezone.utc)
        predicted_end_at = predicted_end_ist.astimezone(timezone.utc)

        return {
            "predicted_start_at": predicted_start_at,
            "predicted_end_at": predicted_end_at,
            "predicted_duration_seconds": pred_duration_sec,
            "uncertainty_minutes": unc_min,
            "model_type": model_type,
            "model_version": model_version,
            "prediction_status": status,
            "features": features,
        }

    def generate_initial_prediction(
        self,
        db: Session,
        queue_entry_id: uuid.UUID,
    ) -> Optional[PredictionSnapshot]:
        """Safely generate initial prediction snapshot when patient joins.

        Graceful degradation: prediction errors are caught so the queue join is never broken.
        """
        try:
            entry = db.query(QueueEntry).filter(QueueEntry.id == queue_entry_id).first()
            if not entry:
                return None

            # If this entry was created via an APPOINTMENT_BOOKED flow the
            # booking event may carry the authoritative appointment_date in
            # its payload. In some race conditions the DB row may still have
            # a default/current date at the time this function runs. Prefer
            # the booked appointment_date from the event when available so
            # predictions are anchored to the intended clinic date.
            join_event = (
                db.query(QueueEvent)
                .filter(
                    QueueEvent.queue_entry_id == entry.id,
                    QueueEvent.event_type == QueueEventType.PATIENT_JOINED.value,
                )
                .first()
            )
            if not join_event:
                booking_event = (
                    db.query(QueueEvent)
                    .filter(
                        QueueEvent.queue_entry_id == entry.id,
                        QueueEvent.event_type == QueueEventType.APPOINTMENT_BOOKED.value,
                    )
                    .first()
                )
                if booking_event and booking_event.payload_json and booking_event.payload_json.get("appointment_date"):
                    try:
                        entry.appointment_date = date.fromisoformat(booking_event.payload_json.get("appointment_date"))
                    except Exception:
                        pass

            # Compute prediction using the (possibly overridden) entry.appointment_date
            calc = self.calculate_entry_prediction(db, entry)

            # Find PATIENT_JOINED event (if any) for attribution
            if 'join_event' not in locals():
                join_event = (
                    db.query(QueueEvent)
                    .filter(
                        QueueEvent.queue_entry_id == entry.id,
                        QueueEvent.event_type == QueueEventType.PATIENT_JOINED.value,
                    )
                    .first()
                )

            text, exp_json = build_explanation(
                event_type=QueueEventType.PATIENT_JOINED.value,
                shift_minutes=0,
                is_meaningful=False,
                payload={},
            )

            snapshot = PredictionSnapshot(
                queue_entry_id=entry.id,
                queue_id=entry.queue_id,
                predicted_start_at=calc["predicted_start_at"],
                predicted_end_at=calc["predicted_end_at"],
                predicted_duration_seconds=calc["predicted_duration_seconds"],
                uncertainty_minutes=calc["uncertainty_minutes"],
                model_type=calc["model_type"],
                model_version=calc["model_version"],
                prediction_status=calc["prediction_status"],
                explanation_text=text,
                explanation_json=exp_json,
                feature_snapshot_json=calc["features"],
                trigger_event_id=join_event.id if join_event else None,
                is_meaningful_change=False,
                shift_minutes=0,
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            return snapshot
        except Exception as e:
            logger.exception("Error generating initial prediction: %s", e)
            db.rollback()
            return None

    def reforecast_after_event(
        self,
        db: Session,
        queue_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> List[PredictionSnapshot]:
        """Dynamically reforecast predictions for all affected downstream patients after an operational event.

        Idempotency:
        - Checks if trigger_event_id has already generated prediction snapshots.
        - If already processed, returns existing snapshots without creating duplicates.
        """
        # 1. Idempotency check
        existing = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.trigger_event_id == event_id)
            .all()
        )
        if existing:
            return existing

        # 2. Fetch triggering event
        event = db.query(QueueEvent).filter(QueueEvent.id == event_id).first()
        if not event or event.event_type not in REFORECAST_TRIGGERS:
            return []

        # 3. Identify affected active patients (WAITING, ARRIVED, and BOOKED)
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        target_date = queue.queue_date if queue and queue.queue_date else None
        if not target_date and event.payload_json and "appointment_date" in event.payload_json:
            try:
                target_date = date.fromisoformat(event.payload_json["appointment_date"])
            except Exception:
                pass

        query = db.query(QueueEntry).filter(
            QueueEntry.queue_id == queue_id,
            QueueEntry.status.in_([
                QueueEntryStatus.WAITING,
                QueueEntryStatus.ARRIVED,
                QueueEntryStatus.BOOKED,
            ]),
        )
        if target_date:
            query = query.filter(QueueEntry.appointment_date == target_date)

        active_entries = query.order_by(QueueEntry.token_number.asc()).all()
        if not active_entries:
            return []

        new_snapshots: List[PredictionSnapshot] = []

        # 4. Recalculate predictions for each affected patient
        for entry in active_entries:

            # Latest previous snapshot for comparison
            prev_snapshot = (
                db.query(PredictionSnapshot)
                .filter(PredictionSnapshot.queue_entry_id == entry.id)
                .order_by(desc(PredictionSnapshot.created_at))
                .first()
            )

            calc = self.calculate_entry_prediction(db, entry)

            # Compute minute shift
            if prev_snapshot:
                p_curr = calc["predicted_start_at"]
                p_prev = prev_snapshot.predicted_start_at
                if p_curr.tzinfo is not None and p_prev.tzinfo is None:
                    p_prev = p_prev.replace(tzinfo=timezone.utc)
                elif p_curr.tzinfo is None and p_prev.tzinfo is not None:
                    p_curr = p_curr.replace(tzinfo=timezone.utc)
                shift_seconds = (p_curr - p_prev).total_seconds()
                shift_minutes = int(round(shift_seconds / 60))
            else:
                shift_minutes = 0

            # Meaningful change check (>= 10 minutes threshold)
            is_meaningful = abs(shift_minutes) >= MEANINGFUL_CHANGE_THRESHOLD_MINUTES

            text, exp_json = build_explanation(
                event_type=event.event_type,
                shift_minutes=shift_minutes,
                is_meaningful=is_meaningful,
                payload=event.payload_json,
            )

            snap = PredictionSnapshot(
                queue_entry_id=entry.id,
                queue_id=queue_id,
                predicted_start_at=calc["predicted_start_at"],
                predicted_end_at=calc["predicted_end_at"],
                predicted_duration_seconds=calc["predicted_duration_seconds"],
                uncertainty_minutes=calc["uncertainty_minutes"],
                model_type=calc["model_type"],
                model_version=calc["model_version"],
                prediction_status=calc["prediction_status"],
                explanation_text=text,
                explanation_json=exp_json,
                feature_snapshot_json=calc["features"],
                trigger_event_id=event.id,
                is_meaningful_change=is_meaningful,
                shift_minutes=shift_minutes,
            )
            db.add(snap)
            new_snapshots.append(snap)

        db.commit()
        for snap in new_snapshots:
            db.refresh(snap)
            # Phase 5: Trigger arrival plan recalculation if origin coordinates configured
            if snap.queue_entry and snap.queue_entry.origin_latitude is not None and snap.queue_entry.origin_longitude is not None:
                try:
                    from app.services.arrival_optimizer import ArrivalOptimizationService
                    ArrivalOptimizationService().calculate_arrival_plan(db, snap.queue_entry, snap)
                except Exception as err:
                    logger.warning("Advisory arrival plan recalculation failed: %s", err)

        # Phase 6: Real-time WebSocket dispatch & notification evaluation
        try:
            from app.services.realtime_dispatcher import RealtimeDispatcher
            RealtimeDispatcher.dispatch_reforecast_updates(db, queue_id, event, new_snapshots)
        except Exception as err:
            logger.warning("Real-time update dispatch failed: %s", err)

        return new_snapshots

