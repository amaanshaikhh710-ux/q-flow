"""Base notification provider interface and payload dataclasses."""

from abc import ABC, abstractmethod
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NotificationPayload(BaseModel):
    """Payload representing an outbound notification."""
    notification_id: uuid.UUID
    recipient: str
    title: str
    message: str
    channel: str = "SMS"
    notification_type: str = "ETA_CHANGED"
    payload: Optional[Dict[str, Any]] = None


class BaseNotificationProvider(ABC):
    """Abstract interface for notification channels (SMS, WhatsApp, Web, Push)."""

    @abstractmethod
    def send(
        self,
        notification_id: uuid.UUID,
        recipient: str,
        title: str,
        message: str,
        channel: str = "SMS",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Deliver notification to recipient. Return True on success, False or raise on error."""
        pass
