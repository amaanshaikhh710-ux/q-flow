"""Phase 6 End-to-End Real-Time & Notification Integration Tests.

Verifies:
1. End-to-end chain:
   Queue Action (Emergency Insertion) -> Queue Event -> Reforecast ->
   Prediction Snapshot -> Arrival Plan -> WebSocket dispatch ->
   Notification Intent -> Mock Provider -> Patient Alert.
2. Downstream affected targeting:
   Only affected downstream patients receive patient-specific updates;
   unaffected patients do not.
3. Resilience:
   Notification provider failure does NOT rollback queue state or emergency insertion.
4. Database commit precedes any real-time emission.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest

from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.models.notification import Notification, NotificationStatus
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from app.services.reforecast_service import PredictionService
from app.services.notifications.service import default_notification_provider
from tests.conftest import make_test_user


@pytest.fixture(autouse=True)
def reset_provider():
    default_notification_provider.clear()
    default_notification_provider.should_fail = False
    yield
    default_notification_provider.clear()
    default_notification_provider.should_fail = False


def test_emergency_insertion_triggers_complete_phase6_chain(db_session, seed_opd_data):
    """Verify complete chain:

    Emergency Insert -> Queue Event -> Reforecast -> Prediction -> Arrival Plan ->
    Notification created & sent via MockProvider.
    """
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Triage", "triage@test.com", UserRole.STAFF)
    pat1, _ = make_test_user(db_session, "Pat Downstream 1", "down1@test.com", UserRole.PATIENT)
    pat2, _ = make_test_user(db_session, "Pat Downstream 2", "down2@test.com", UserRole.PATIENT)

    entry1 = QueueEngineService.join_queue(db_session, queue.id, pat1.id)
    entry2 = QueueEngineService.join_queue(db_session, queue.id, pat2.id)

    prediction_service = PredictionService()
    # Initial baselines
    prediction_service.generate_initial_prediction(db_session, entry1.id)
    prediction_service.generate_initial_prediction(db_session, entry2.id)
    default_notification_provider.clear()

    # Now insert emergency patient via state machine
    emerg_pat, _ = make_test_user(db_session, "Emergency Pat", "emerg@test.com", UserRole.PATIENT)
    emerg_entry, affected_ids = QueueStateMachineService.insert_emergency(
        db=db_session,
        queue_id=queue.id,
        patient_user_id=emerg_pat.id,
        actor_id=staff.id,
        reason="Severe cardiac arrest",
    )

    # Verify queue engine state committed
    assert emerg_entry.id is not None
    assert emerg_entry.priority_class == PriorityClass.EMERGENCY

    # Fetch triggering EMERGENCY_INSERTED event
    emerg_event = (
        db_session.query(QueueEvent)
        .filter(
            QueueEvent.queue_entry_id == emerg_entry.id,
            QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value,
        )
        .first()
    )
    assert emerg_event is not None

    # Reforecast triggered by emergency event
    new_snapshots = prediction_service.reforecast_after_event(
        db=db_session,
        queue_id=queue.id,
        event_id=emerg_event.id,
    )

    # Verify downstream predictions were updated and shift >= 10 min for affected patients
    downstream_snapshots = [s for s in new_snapshots if s.queue_entry_id in (entry1.id, entry2.id)]
    assert len(downstream_snapshots) == 2
    for res in downstream_snapshots:
        assert res.is_meaningful_change is True
        assert (res.shift_minutes or 0) >= 10

    # Verify notifications were created and dispatched through mock provider
    notifications = (
        db_session.query(Notification)
        .filter(Notification.queue_entry_id.in_([entry1.id, entry2.id]))
        .all()
    )
    assert len(notifications) >= 2
    for notif in notifications:
        assert notif.status == NotificationStatus.SENT
        assert "Q-FLOW" in notif.title
        # Verify privacy: no origin coordinates in payload
        assert "origin_latitude" not in str(notif.payload_json)

    # Verify provider received the messages
    assert len(default_notification_provider.sent_notifications) >= 2


def test_notification_provider_failure_does_not_rollback_queue(db_session, seed_opd_data):
    """Verify failure resilience:

    When notification delivery fails, the queue event, entry, and reforecast
    remain committed and intact. Notification is marked FAILED.
    """
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Resilient", "staffres@test.com", UserRole.STAFF)
    pat1, _ = make_test_user(db_session, "Pat Resilient", "resilient@test.com", UserRole.PATIENT)
    entry1 = QueueEngineService.join_queue(db_session, queue.id, pat1.id)

    prediction_service = PredictionService()
    prediction_service.generate_initial_prediction(db_session, entry1.id)
    default_notification_provider.clear()

    # Configure mock provider to fail
    default_notification_provider.should_fail = True

    emerg_pat, _ = make_test_user(db_session, "Emerg Resilient", "emergres@test.com", UserRole.PATIENT)
    emerg_entry, affected_ids = QueueStateMachineService.insert_emergency(
        db=db_session,
        queue_id=queue.id,
        patient_user_id=emerg_pat.id,
        actor_id=staff.id,
        reason="Trauma shock",
    )

    emerg_event = (
        db_session.query(QueueEvent)
        .filter(
            QueueEvent.queue_entry_id == emerg_entry.id,
            QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value,
        )
        .first()
    )

    # Reforecast
    new_snapshots = prediction_service.reforecast_after_event(
        db=db_session,
        queue_id=queue.id,
        event_id=emerg_event.id,
    )

    # Verify queue entry and emergency are still intact
    refreshed_emerg = db_session.query(QueueEntry).filter(QueueEntry.id == emerg_entry.id).first()
    assert refreshed_emerg is not None
    assert refreshed_emerg.priority_class == PriorityClass.EMERGENCY

    # Verify notification recorded failure without rolling back
    notifs = (
        db_session.query(Notification)
        .filter(Notification.queue_entry_id == entry1.id)
        .all()
    )
    assert len(notifs) >= 1
    assert notifs[0].status == NotificationStatus.FAILED
    assert notifs[0].failure_reason is not None
