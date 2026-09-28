"""Service tests for ArrivalOptimizationService formulas, uncertainty, threshold, and reforecast integration."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest

from app.models.user import UserRole
from app.models.queue_entry import QueueEntry, QueueEntryStatus
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.services.arrival_optimizer import ArrivalOptimizationService
from app.services.travel.mock_provider import MockTravelProvider
from app.services.reforecast_service import PredictionService
from app.services.queue_engine import QueueEngineService
from app.services.queue_state_machine import QueueStateMachineService
from tests.conftest import make_test_user


def test_arrival_and_departure_formula_exact_example(db_session, seed_opd_data):
    """Verify exact formula from specification:
    Consultation: 4:35 PM – 4:55 PM
    Travel: 30 min duration + 5 min uncertainty = 35 min
    Arrival Window: 4:20 PM – 4:30 PM (10-min buffer)
    Departure Window: 3:45 PM – 3:55 PM
    """
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Formula Pat", "formulatest@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    # Fixed anchor: 4:35 PM UTC
    base_time = datetime(2026, 9, 19, 16, 35, 0, tzinfo=timezone.utc)
    pred_snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=base_time,                                # 4:35 PM
        predicted_end_at=base_time + timedelta(minutes=20),          # 4:55 PM
        predicted_duration_seconds=900,                              # 15 mins
        uncertainty_minutes=5,
        model_type="robust_median",
        model_version="baseline-v1",
        prediction_status="VALID",
    )
    db_session.add(pred_snapshot)
    db_session.commit()

    # Mock provider: 30 min duration (1800s), 5 min uncertainty (300s)
    mock_provider = MockTravelProvider(default_duration_seconds=1800, default_uncertainty_seconds=300)
    optimizer = ArrivalOptimizationService(travel_provider=mock_provider)

    plan = optimizer.calculate_arrival_plan(db_session, entry, pred_snapshot, buffer_minutes=10)

    # 1. Arrival Window Check: 4:20 PM – 4:30 PM
    expected_arrival_end = base_time - timedelta(minutes=5)          # 4:30 PM
    expected_arrival_start = base_time - timedelta(minutes=15)       # 4:20 PM
    p_arr_start = plan.arrival_start_at.replace(tzinfo=timezone.utc) if plan.arrival_start_at.tzinfo is None else plan.arrival_start_at
    p_arr_end = plan.arrival_end_at.replace(tzinfo=timezone.utc) if plan.arrival_end_at.tzinfo is None else plan.arrival_end_at
    assert p_arr_start == expected_arrival_start
    assert p_arr_end == expected_arrival_end

    # 2. Departure Window Check: 3:45 PM – 3:55 PM
    # Total travel allowance = 30m + 5m = 35m
    expected_departure_start = expected_arrival_start - timedelta(minutes=35) # 4:20 - 35m = 3:45 PM
    expected_departure_end = expected_arrival_end - timedelta(minutes=35)     # 4:30 - 35m = 3:55 PM
    p_dep_start = plan.departure_start_at.replace(tzinfo=timezone.utc) if plan.departure_start_at.tzinfo is None else plan.departure_start_at
    p_dep_end = plan.departure_end_at.replace(tzinfo=timezone.utc) if plan.departure_end_at.tzinfo is None else plan.departure_end_at
    assert p_dep_start == expected_departure_start
    assert p_dep_end == expected_departure_end

    assert plan.travel_status in ("OPTIMIZED", "AVAILABLE")
    assert plan.travel_duration_seconds == 1800
    assert plan.travel_uncertainty_seconds == 300


def test_arrival_optimization_without_travel_origin(db_session, seed_opd_data):
    """Verify arrival optimizer returns UNAVAILABLE when patient has not set an origin without breaking prediction."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "No Origin Pat", "noorigin@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    # Entry has origin_latitude=None, origin_longitude=None

    now = datetime.now(timezone.utc)
    pred_snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=45),
        predicted_end_at=now + timedelta(minutes=65),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(pred_snapshot)
    db_session.commit()

    optimizer = ArrivalOptimizationService(travel_provider=MockTravelProvider())
    plan = optimizer.calculate_arrival_plan(db_session, entry, pred_snapshot)

    assert plan.travel_status == "UNAVAILABLE"
    assert plan.arrival_start_at is None
    assert plan.departure_start_at is None
    assert "Add your starting location" in plan.explanation


def test_meaningful_change_threshold_on_arrival_plan(db_session, seed_opd_data):
    """Verify that shifts >= 10 minutes mark is_meaningful_change=True, and < 10 mins mark False."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Thresh Pat", "threshpat@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snap1 = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=60),
        predicted_end_at=now + timedelta(minutes=80),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snap1)
    db_session.commit()

    optimizer = ArrivalOptimizationService(travel_provider=MockTravelProvider())
    plan1 = optimizer.calculate_arrival_plan(db_session, entry, snap1)
    assert plan1.is_meaningful_change is False

    # Shift 1: minor shift (+5 minutes) -> not meaningful
    snap2 = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=65),
        predicted_end_at=now + timedelta(minutes=85),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snap2)
    db_session.commit()
    plan2 = optimizer.calculate_arrival_plan(db_session, entry, snap2)
    assert plan2.is_meaningful_change is False
    assert plan2.consultation_changed is False

    # Shift 2: major shift (+15 minutes from snap1) -> meaningful
    snap3 = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=80),
        predicted_end_at=now + timedelta(minutes=100),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snap3)
    db_session.commit()
    plan3 = optimizer.calculate_arrival_plan(db_session, entry, snap3)
    assert plan3.is_meaningful_change is True
    assert plan3.consultation_changed is True


def test_reforecast_triggers_arrival_plan_update(db_session, seed_opd_data):
    """Verify that queue disruption event (emergency insertion) updates arrival and departure recommendation."""
    queue = seed_opd_data["queue"]
    staff, _ = make_test_user(db_session, "Staff Ref Arrive", "staffrefarr@test.com", UserRole.STAFF)
    p_waiting, _ = make_test_user(db_session, "Wait Pat Arrive", "waitarr@test.com", UserRole.PATIENT)
    p_emerg, _ = make_test_user(db_session, "Emerg Pat Arrive", "emergarr@test.com", UserRole.PATIENT)

    # Waiting patient joins and sets origin
    entry = QueueEngineService.join_queue(db_session, queue.id, p_waiting.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    pred_service = PredictionService()
    init_snap = pred_service.generate_initial_prediction(db_session, entry.id)
    assert init_snap is not None

    # Calculate initial arrival plan
    optimizer = ArrivalOptimizationService(travel_provider=MockTravelProvider())
    init_plan = optimizer.calculate_arrival_plan(db_session, entry, init_snap)
    assert init_plan.departure_start_at is not None
    init_dep = init_plan.departure_start_at

    # Emergency patient inserted ahead
    QueueStateMachineService.insert_emergency(db_session, queue.id, p_emerg.id, staff.id, reason="Severe trauma")

    emerg_event = (
        db_session.query(QueueEvent)
        .filter(QueueEvent.queue_id == queue.id, QueueEvent.event_type == QueueEventType.EMERGENCY_INSERTED.value)
        .first()
    )

    # Trigger reforecast
    reforecasted = pred_service.reforecast_after_event(db_session, queue.id, emerg_event.id)
    assert len(reforecasted) >= 1

    # Check latest arrival plan for waiting patient
    latest_plan = (
        db_session.query(ArrivalPlan)
        .filter(ArrivalPlan.queue_entry_id == entry.id)
        .order_by(ArrivalPlan.created_at.desc())
        .first()
    )
    assert latest_plan is not None
    # Because emergency patient was inserted ahead, departure window moved later
    assert latest_plan.departure_start_at > init_dep
    assert latest_plan.is_meaningful_change is True
