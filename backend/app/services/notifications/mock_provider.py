"""Mock notification provider for local development, CI, and testing."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.services.notifications.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class NotificationDeliveryError(Exception):
    """Raised when notification delivery fails."""
    pass


class MockNotificationProvider(BaseNotificationProvider):
    """In-memory mock provider recording sent notifications for audit and testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent_notifications: List[Dict[str, Any]] = []

    def send(
        self,
        notification_id: uuid.UUID,
        recipient: str,
        title: str,
        message: str,
        channel: str = "SMS",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Simulate notification dispatch. Records payload or simulates provider failure."""
        if self.should_fail:
            logger.warning("Mock notification delivery simulated failure for %s", notification_id)
            raise NotificationDeliveryError("Simulated notification gateway timeout/failure")

        record = {
            "notification_id": str(notification_id),
            "recipient": recipient,
            "title": title,
            "message": message,
            "channel": channel,
            "payload": payload or {},
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sent_notifications.append(record)
        logger.info("Mock notification delivered: ID %s, channel %s, recipient %s", notification_id, channel, recipient)
        return True

    def clear(self) -> None:
        """Clear recorded notifications."""
        self.sent_notifications.clear()
