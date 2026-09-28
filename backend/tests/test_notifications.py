"""Tests for Phase 6 Notification Intent System and Mock Provider."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest

from app.core.config import settings
from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.notification import Notification, NotificationStatus
from app.services.notifications.mock_provider import MockNotificationProvider
from app.services.notifications.service import NotificationService, default_notification_provider
from app.services.queue_engine import QueueEngineService
from tests.conftest import make_test_user


@pytest.fixture(autouse=True)
def clear_mock_notifications():
    """Clear mock notification records between tests."""
    default_notification_provider.clear()
    default_notification_provider.should_fail = False
    yield
    default_notification_provider.clear()
    default_notification_provider.should_fail = False


def test_meaningful_shift_creates_and_dispatches_notification(db_session, seed_opd_data):
    """Requirement 21: Shift >= 10 minutes creates and sends notification."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 1", "notif1@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    now = datetime.now(timezone.utc)
    event = QueueEvent(
        queue_id=queue.id,
        queue_entry_id=entry.id,
        actor_user_id=patient.id,
        event_type=QueueEventType.EMERGENCY_INSERTED.value,
        event_time=now,
        payload_json={"reason": "Cardiac trauma"},
    )
    db_session.add(event)
    db_session.commit()

    # Snapshot with +15 min shift (meaningful)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=60),
        predicted_end_at=now + timedelta(minutes=80),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        trigger_event_id=event.id,
        is_meaningful_change=True,
        shift_minutes=15,
        explanation_text="An emergency patient was inserted ahead of you.",
    )
    db_session.add(snapshot)
    db_session.commit()

    service = NotificationService(provider=default_notification_provider)
    notif = service.evaluate_and_send_reforecast_notification(db_session, snapshot, event)

    assert notif is not None
    assert notif.status == NotificationStatus.SENT.value
    assert notif.sent_at is not None
    assert notif.title == "Your Q-FLOW wait time changed"
    assert "now" in notif.message.lower()
    assert "An emergency patient was inserted" in notif.message

    # Verify provider recorded it
    assert len(default_notification_provider.sent_notifications) == 1
    sent = default_notification_provider.sent_notifications[0]
    assert sent["title"] == "Your Q-FLOW wait time changed"
    assert "payload" in sent


def test_minor_shift_does_not_create_notification(db_session, seed_opd_data):
    """Requirement 22: Shift < 10 minutes does NOT create notification."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 2", "notif2@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=50),
        predicted_end_at=now + timedelta(minutes=70),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        is_meaningful_change=False,
        shift_minutes=5,  # Minor change
        explanation_text="Doctor pacing adjustment.",
    )
    db_session.add(snapshot)
    db_session.commit()

    service = NotificationService(provider=default_notification_provider)
    notif = service.evaluate_and_send_reforecast_notification(db_session, snapshot)

    assert notif is None
    assert len(default_notification_provider.sent_notifications) == 0


def test_meaningful_negative_shift_creates_earlier_notification(db_session, seed_opd_data):
    """Requirement 23: Meaningful negative shift (-10 min) creates notification informing patient ETA moved earlier."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 3", "notif3@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=30),
        predicted_end_at=now + timedelta(minutes=50),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        is_meaningful_change=True,
        shift_minutes=-12,  # Moved earlier
        explanation_text="A patient ahead was marked no-show.",
    )
    db_session.add(snapshot)
    db_session.commit()

    service = NotificationService(provider=default_notification_provider)
    notif = service.evaluate_and_send_reforecast_notification(db_session, snapshot)

    assert notif is not None
    assert notif.status == NotificationStatus.SENT.value
    assert "moved earlier" in notif.message.lower()


def test_notification_idempotency_prevents_duplicates(db_session, seed_opd_data):
    """Requirement 24: Same (entry_id, trigger_event_id, notification_type) does not generate duplicate notifications."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 4", "notif4@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    now = datetime.now(timezone.utc)
    event = QueueEvent(
        queue_id=queue.id,
        queue_entry_id=entry.id,
        actor_user_id=patient.id,
        event_type=QueueEventType.EMERGENCY_INSERTED.value,
        event_time=now,
    )
    db_session.add(event)
    db_session.commit()

    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=60),
        predicted_end_at=now + timedelta(minutes=80),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        trigger_event_id=event.id,
        is_meaningful_change=True,
        shift_minutes=15,
        explanation_text="Emergency inserted.",
    )
    db_session.add(snapshot)
    db_session.commit()

    service = NotificationService(provider=default_notification_provider)

    # First evaluation -> creates notification
    notif1 = service.evaluate_and_send_reforecast_notification(db_session, snapshot, event)
    assert notif1 is not None
    assert len(default_notification_provider.sent_notifications) == 1

    # Second evaluation -> idempotent, returns existing, does NOT dispatch duplicate
    notif2 = service.evaluate_and_send_reforecast_notification(db_session, snapshot, event)
    assert notif2.id == notif1.id
    assert len(default_notification_provider.sent_notifications) == 1

    # DB records count should be exactly 1
    count = (
        db_session.query(Notification)
        .filter(Notification.queue_entry_id == entry.id, Notification.trigger_event_id == event.id)
        .count()
    )
    assert count == 1


def test_provider_failure_marks_failed_without_rollback(db_session, seed_opd_data):
    """Requirement 26 & 27: Provider failure records status=failed without breaking caller or rolling back."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 5", "notif5@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)

    failing_provider = MockNotificationProvider(should_fail=True)
    service = NotificationService(provider=failing_provider)

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=60),
        predicted_end_at=now + timedelta(minutes=80),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        is_meaningful_change=True,
        shift_minutes=15,
        explanation_text="Doctor delay.",
    )
    db_session.add(snapshot)
    db_session.commit()

    # Must NOT raise exception to caller
    notif = service.evaluate_and_send_reforecast_notification(db_session, snapshot)

    assert notif is not None
    assert notif.status == NotificationStatus.FAILED.value
    assert notif.failed_at is not None
    assert "Simulated notification gateway" in notif.failure_reason

    # Ensure queue entry and snapshot are completely intact in DB
    refreshed_entry = db_session.query(QueueEntry).filter(QueueEntry.id == entry.id).first()
    assert refreshed_entry.status == QueueEntryStatus.WAITING


def test_notification_content_privacy_and_safety(db_session, seed_opd_data):
    """Requirements 29 & 30: Notification does not leak coordinates, tokens, or internal IDs."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Notif Pat 6", "notif6@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=60),
        predicted_end_at=now + timedelta(minutes=80),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
        is_meaningful_change=True,
        shift_minutes=15,
        explanation_text="Emergency inserted.",
    )
    db_session.add(snapshot)
    db_session.commit()

    service = NotificationService(provider=default_notification_provider)
    notif = service.evaluate_and_send_reforecast_notification(db_session, snapshot)

    # Invariants: Coordinates must NEVER appear in notification message or payload
    assert "12.9352" not in notif.message
    assert "77.6245" not in notif.message
    assert str(patient.id) not in notif.message
    assert "origin_latitude" not in str(notif.payload_json)
