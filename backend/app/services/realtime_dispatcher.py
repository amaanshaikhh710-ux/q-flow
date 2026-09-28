"""Real-time update dispatcher connecting authoritative queue events to WebSockets and notifications."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Coroutine
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.queue_event import QueueEvent
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.websocket.manager import connection_manager
from app.services.notifications.service import NotificationService

logger = logging.getLogger(__name__)


def safe_run_async(coro: Coroutine) -> None:
    """Safely schedule or execute an async coroutine from synchronous service code."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            asyncio.run(coro)
    except RuntimeError:
        asyncio.run(coro)
    except Exception as e:
        logger.warning("Failed to schedule real-time async dispatch: %s", e)


class RealtimeDispatcher:
    """Dispatches real-time updates and notification intents after authoritative state commits."""

    @staticmethod
    def dispatch_reforecast_updates(
        db: Session,
        queue_id: uuid.UUID,
        event: Optional[QueueEvent],
        new_snapshots: List[PredictionSnapshot],
    ) -> None:
        """Called AFTER database commit to broadcast WebSocket updates and evaluate notifications.

        Targeting Rule:
        - Patient-specific updates are sent ONLY to affected entries.
        - Staff receive a queue-level reforecast event.
        - Notification intents are evaluated for snapshots meeting meaningful threshold.
        """
        if not new_snapshots:
            return

        notification_service = NotificationService()
        now_iso = datetime.now(timezone.utc).isoformat()
        reason_code = event.event_type if event else "QUEUE_REFORECAST"

        for snap in new_snapshots:
            entry_id = snap.queue_entry_id

            # 1. Evaluate Notification Intent (>= 10 min meaningful shift)
            try:
                notification_service.evaluate_and_send_reforecast_notification(db, snap, event)
            except Exception as e:
                logger.warning("Notification intent evaluation failed for entry %s: %s", entry_id, e)

            # 2. Fetch latest arrival plan for this entry
            latest_plan = (
                db.query(ArrivalPlan)
                .filter(ArrivalPlan.queue_entry_id == entry_id)
                .order_by(desc(ArrivalPlan.created_at))
                .first()
            )

            plan_payload = None
            if latest_plan:
                plan_payload = {
                    "arrival_start_at": latest_plan.arrival_start_at.isoformat() if latest_plan.arrival_start_at else None,
                    "arrival_end_at": latest_plan.arrival_end_at.isoformat() if latest_plan.arrival_end_at else None,
                    "departure_start_at": latest_plan.departure_start_at.isoformat() if latest_plan.departure_start_at else None,
                    "departure_end_at": latest_plan.departure_end_at.isoformat() if latest_plan.departure_end_at else None,
                    "travel_status": latest_plan.travel_status,
                }

            # 3. Assemble typed, patient-safe QUEUE_REFORECAST message
            msg = {
                "type": "QUEUE_REFORECAST",
                "version": 1,
                "timestamp": now_iso,
                "entry_id": str(entry_id),
                "queue_id": str(queue_id),
                "prediction": {
                    "predicted_start_at": snap.predicted_start_at.isoformat(),
                    "predicted_end_at": snap.predicted_end_at.isoformat(),
                    "uncertainty_seconds": snap.uncertainty_margin_seconds,
                    "patients_ahead": snap.patients_ahead_count,
                    "predicted_duration_minutes": int(round(snap.predicted_duration_seconds / 60)),
                },
                "arrival_plan": plan_payload,
                "explanation": {
                    "reason_code": reason_code,
                    "message": snap.explanation_text or "Your estimated consultation window has been updated.",
                },
            }

            # 4. Dispatch to patient WebSocket connections
            safe_run_async(connection_manager.send_to_patient(entry_id, msg))

        # 5. Broadcast queue-level reforecast event to staff connections
        staff_event = {
            "type": "QUEUE_REFORECAST",
            "version": 1,
            "timestamp": now_iso,
            "queue_id": str(queue_id),
            "payload": {
                "event_type": reason_code,
                "affected_entries_count": len(new_snapshots),
                "timestamp": now_iso,
            },
        }
        safe_run_async(connection_manager.broadcast_to_queue(queue_id, staff_event))
