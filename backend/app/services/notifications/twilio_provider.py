"""Twilio SMS notification provider for real-world SMS delivery."""

import uuid
import logging
from typing import Optional, Dict, Any
import httpx

from app.core.config import settings
from app.services.notifications.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class NotificationDeliveryError(Exception):
    """Raised when notification delivery fails."""
    pass


class TwilioNotificationProvider(BaseNotificationProvider):
    """Production SMS provider integrating with Twilio REST API."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_phone: Optional[str] = None,
    ):
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.from_phone = from_phone or settings.TWILIO_PHONE_NUMBER

    def is_configured(self) -> bool:
        """Check if required Twilio credentials are present."""
        return bool(self.account_sid and self.auth_token and self.from_phone)

    def send(
        self,
        notification_id: uuid.UUID,
        recipient: str,
        title: str,
        message: str,
        channel: str = "SMS",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send an SMS notification via Twilio REST API."""
        if not self.is_configured():
            err_msg = (
                "CONFIGURATION REQUIRED: Twilio credentials not configured. "
                "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in environment."
            )
            logger.warning("Twilio dispatch blocked for notification %s: %s", notification_id, err_msg)
            raise NotificationDeliveryError(err_msg)

        # Ensure recipient is a phone number
        cleaned_recipient = recipient.strip()
        if not cleaned_recipient.startswith("+") and cleaned_recipient.isdigit():
            # Default to India country code +91 if 10-digit number
            if len(cleaned_recipient) == 10:
                cleaned_recipient = f"+91{cleaned_recipient}"
            else:
                cleaned_recipient = f"+{cleaned_recipient}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        body = f"{title}: {message}" if title else message

        data = {
            "From": self.from_phone,
            "To": cleaned_recipient,
            "Body": body,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )
                if response.status_code in (200, 201):
                    logger.info("Twilio SMS sent successfully for notification %s to %s", notification_id, cleaned_recipient)
                    return True
                else:
                    error_detail = response.text
                    logger.error("Twilio SMS delivery failed (%d): %s", response.status_code, error_detail)
                    raise NotificationDeliveryError(f"Twilio API error {response.status_code}: {error_detail}")
        except httpx.RequestError as e:
            logger.error("Network error connecting to Twilio: %s", e)
            raise NotificationDeliveryError(f"Twilio network error: {e}")
