"""Notification service managing intent generation, threshold evaluation, idempotency, and dispatch."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.queue_entry import QueueEntry
from app.models.queue_event import QueueEvent
from app.services.notifications.base import BaseNotificationProvider
from app.services.notifications.mock_provider import MockNotificationProvider
from app.services.notifications.twilio_provider import TwilioNotificationProvider

logger = logging.getLogger(__name__)

# Global mock provider instance for application & testing
default_notification_provider = MockNotificationProvider()


def get_notification_provider() -> BaseNotificationProvider:
    """Return the active notification provider based on settings."""
    provider_name = (settings.NOTIFICATION_PROVIDER or settings.SMS_PROVIDER or "mock").lower()
    if provider_name == "twilio":
        return TwilioNotificationProvider()
    return default_notification_provider


class NotificationService:
    """Service to evaluate notification intents and dispatch patient alerts safely."""

    def __init__(self, provider: Optional[BaseNotificationProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> BaseNotificationProvider:
        if self._provider is None:
            return get_notification_provider()
        return self._provider

    def evaluate_and_send_reforecast_notification(
        self,
        db: Session,
        snapshot: PredictionSnapshot,
        event: Optional[QueueEvent] = None,
    ) -> Optional[Notification]:
        """Evaluate if an ETA shift requires patient notification, enforce idempotency, and dispatch.

        Rules:
        - Threshold: abs(shift_minutes) >= 10 (or snapshot.is_meaningful_change is True).
        - Idempotency: Deduplicated by (queue_entry_id, trigger_event_id, notification_type).
        - Safety: Provider failures never roll back queue operations or raise exceptions out.
        """
        # 1. Meaningful shift threshold check
        threshold_minutes = settings.ETA_NOTIFICATION_THRESHOLD_MINUTES
        shift = snapshot.shift_minutes or 0
        if not snapshot.is_meaningful_change and abs(shift) < threshold_minutes:
            logger.debug("Shift of %d minutes does not meet notification threshold (%d min)", shift, threshold_minutes)
            return None

        entry = snapshot.queue_entry
        if not entry or not entry.patient_user_id:
            entry = db.query(QueueEntry).filter(QueueEntry.id == snapshot.queue_entry_id).first()
            if not entry or not entry.patient_user_id:
                return None

        # 2. Deterministic Idempotency Check: (queue_entry_id, trigger_event_id, notification_type)
        trigger_id = snapshot.trigger_event_id or (event.id if event else None)
        notification_type = "ETA_CHANGED"

        if trigger_id:
            existing = (
                db.query(Notification)
                .filter(
                    Notification.queue_entry_id == entry.id,
                    Notification.trigger_event_id == trigger_id,
                    Notification.notification_type == notification_type,
                )
                .first()
            )
            if existing:
                logger.info("Notification for entry %s and trigger %s already exists. Skipping duplicate.", entry.id, trigger_id)
                return existing

        # 3. Construct patient-friendly notification copy
        start_str = snapshot.predicted_start_at.strftime("%I:%M %p").lstrip("0")
        end_str = snapshot.predicted_end_at.strftime("%I:%M %p").lstrip("0")
        window_str = f"{start_str}–{end_str}"

        reason_text = snapshot.explanation_text or "Queue schedule updated."
        title = "Your Q-FLOW wait time changed"

        if shift > 0:
            message = f"Your estimated consultation window is now {window_str}. Reason: {reason_text}"
        elif shift < 0:
            message = f"Your estimated consultation window has moved earlier to {window_str}. Reason: {reason_text}"
        else:
            message = f"Your estimated consultation window is {window_str}. Reason: {reason_text}"

        recipient = "patient"
        if getattr(entry, "patient", None):
            recipient = entry.patient.phone or entry.patient.email or f"user-{entry.patient.id}"

        safe_payload = {
            "shift_minutes": shift,
            "predicted_start_at": snapshot.predicted_start_at.isoformat(),
            "predicted_end_at": snapshot.predicted_end_at.isoformat(),
            "reason": reason_text,
        }

        # 4. Record Notification in DB (Initial Status: PENDING)
        notification = Notification(
            user_id=entry.patient_user_id,
            queue_entry_id=entry.id,
            trigger_event_id=trigger_id,
            channel=NotificationChannel.SMS.value,
            notification_type=notification_type,
            title=title,
            message=message,
            payload_json=safe_payload,
            status=NotificationStatus.PENDING.value,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        # 5. Dispatch through provider (wrapped in try/except)
        now = datetime.now(timezone.utc)
        try:
            self.provider.send(
                notification_id=notification.id,
                recipient=recipient,
                title=title,
                message=message,
                channel=notification.channel,
                payload=safe_payload,
            )
            notification.status = NotificationStatus.SENT.value
            notification.sent_at = now
        except Exception as e:
            logger.warning("Notification delivery failed for ID %s: %s", notification.id, e)
            notification.status = NotificationStatus.FAILED.value
            notification.failed_at = now
            notification.failure_reason = str(e)

        db.commit()
        db.refresh(notification)

        # Broadcast to user websocket
        try:
            from app.websocket.manager import connection_manager
            from app.services.realtime_dispatcher import safe_run_async
            notif_msg = {
                "type": "NOTIFICATION_CREATED",
                "version": 1,
                "timestamp": now.isoformat(),
                "notification": {
                    "id": str(notification.id),
                    "title": notification.title,
                    "message": notification.message,
                    "notification_type": notification.notification_type,
                    "channel": notification.channel,
                    "status": notification.status,
                    "created_at": notification.created_at.isoformat() if notification.created_at else now.isoformat(),
                    "payload_json": notification.payload_json,
                },
            }
            safe_run_async(connection_manager.send_to_user(entry.patient_user_id, notif_msg))
        except Exception:
            pass

        return notification

    def send_in_app_notification(
        self,
        db: Session,
        user_id: uuid.UUID,
        queue_entry_id: Optional[uuid.UUID],
        title: str,
        message: str,
        notification_type: str = "IN_APP",
        payload: Optional[dict] = None,
    ) -> Notification:
        """Create and store an in-app notification in DB and stream to user WebSocket."""
        from app.websocket.manager import connection_manager
        from app.services.realtime_dispatcher import safe_run_async

        now = datetime.now(timezone.utc)
        notification = Notification(
            user_id=user_id,
            queue_entry_id=queue_entry_id,
            channel="WEB",
            notification_type=notification_type,
            title=title,
            message=message,
            payload_json=payload or {},
            status="delivered",
            delivered_at=now,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)

        # Broadcast to user WebSocket
        try:
            notif_msg = {
                "type": "NOTIFICATION_CREATED",
                "version": 1,
                "timestamp": now.isoformat(),
                "notification": {
                    "id": str(notification.id),
                    "title": notification.title,
                    "message": notification.message,
                    "notification_type": notification.notification_type,
                    "channel": notification.channel,
                    "status": notification.status,
                    "created_at": notification.created_at.isoformat() if notification.created_at else now.isoformat(),
                    "payload_json": notification.payload_json,
                },
            }
            safe_run_async(connection_manager.send_to_user(user_id, notif_msg))
        except Exception as e:
            logger.warning("Failed to broadcast in-app notification: %s", e)

        return notification


