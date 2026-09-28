"""Notification API endpoints for patient in-app notifications and delivery tracking."""

import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.notification import Notification

router = APIRouter()


class NotificationItem(BaseModel):
    id: uuid.UUID
    queue_entry_id: Optional[uuid.UUID] = None
    trigger_event_id: Optional[uuid.UUID] = None
    channel: str
    notification_type: str
    title: Optional[str] = None
    message: Optional[str] = None
    payload_json: Optional[dict] = None
    status: str
    failure_reason: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    total: int


@router.get("/my", response_model=NotificationListResponse)
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    """Return all notifications for the authenticated user ordered by latest first."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

    items = [NotificationItem.model_validate(n) for n in notifications]
    return NotificationListResponse(
        items=items,
        total=len(items),
    )
