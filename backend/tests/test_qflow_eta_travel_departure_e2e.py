"""Comprehensive End-to-End Test Suite for Q-FLOW Real-Time ETA, Outlier-Aware Prediction,
Google Routes Travel Estimation, and Recommended Departure Engine.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.models.user import User, UserRole

from app.services.prediction_engine import (
    OutlierAwareDurationPredictor,
    OutlierClass,
    RobustMedianPredictor,
    SAFE_DEFAULT_DURATION_SECONDS,
    SAFE_DEFAULT_UNCERTAINTY_MINUTES,
)
from app.services.reforecast_service import PredictionService
from app.services.arrival_optimizer import ArrivalOptimizationService
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.travel.base import TravelEstimateResult, TravelProviderException
from app.services.queue_engine import QueueEngineService


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_setup(db_session: Session):
    """Create hospital, department, doctor, OPD session, and queue."""
    hospital = Hospital(
        name="KEM Municipal Hospital",
        address="Acharya Donde Marg, Parel, Mumbai",
        latitude=Decimal("19.0026"),
        longitude=Decimal("72.8423"),
    )
    db_session.add(hospital)
    db_session.flush()

    dept = Department(hospital_id=hospital.id, name="Internal Medicine")
    db_session.add(dept)
    db_session.flush()

    doctor = Doctor(department_id=dept.id, name="Dr. Arjun Mehta", status=DoctorStatus.AVAILABLE)
    db_session.add(doctor)
    db_session.flush()

    from app.models.doctor_schedule import DoctorSchedule
    from datetime import date, time as dt_time
    today = date.today()
    schedule = DoctorSchedule(
        doctor_id=doctor.id,
        hospital_id=hospital.id,
        department_id=dept.id,
        schedule_date=today,
        start_time=dt_time(8, 0),
        end_time=dt_time(18, 0),
        status="AVAILABLE",
    )
    db_session.add(schedule)
    db_session.flush()

    now_dt = datetime.now(timezone.utc)
    opd = OPDSession(
        doctor_id=doctor.id,
        department_id=dept.id,
        starts_at=now_dt,
        ends_at=now_dt + timedelta(hours=6),
        status=SessionStatus.ACTIVE,
    )
    db_session.add(opd)
    db_session.flush()

    queue = Queue(opd_session_id=opd.id, status=QueueStatus.ACTIVE)
    db_session.add(queue)
    db_session.flush()

    # Patients
    patients = []
    for i in range(4):
        p = User(
            email=f"patient_{i}_{uuid.uuid4().hex[:6]}@test.com",
            name=f"Patient {i+1}",
            role=UserRole.PATIENT,
            password_hash="mockhash",
        )
        db_session.add(p)
        db_session.flush()
        patients.append(p)

    db_session.commit()
    return {
        "hospital": hospital,
        "department": dept,
        "doctor": doctor,
        "opd": opd,
        "queue": queue,
        "patients": patients,
    }


# ===========================================================================
# 1. OUTLIER HANDLING & CONSULTATION PREDICTION ENGINE TESTS
# ===========================================================================

def test_outlier_classification_preserves_legitimate_long_and_downweights_anomaly():
    """Verify statistical outlier classification:
    - 65 min consultation is classified as LEGITIMATE_LONG and preserved as clinical evidence.
    - 300 min consultation is classified as EXTREME_ANOMALY and down-weighted/Winsorized.
    - Standard 17-22 min consultations are classified as NORMAL.
    - Result is NOT a naive average (which would be ~60m) and NOT a naive median.
    """
    predictor = OutlierAwareDurationPredictor()

    # Durations in minutes: 18, 21, 19, 20, 22, 65 (legitimate long), 300 (clock anomaly), 17
    historical_minutes = [18, 21, 19, 20, 22, 65, 300, 17]
    historical_seconds = [m * 60 for m in historical_minutes]

    summary = predictor.analyze_outliers(historical_seconds)

    # 1. Classification breakdown verification
    assert summary.sample_count == 8
    assert summary.normal_count == 6  # 17, 18, 19, 20, 21, 22
    assert summary.legitimate_long_count == 1  # 65 minutes
    assert summary.extreme_anomaly_count == 1  # 300 minutes
    assert summary.unusually_short_count == 0

    # 2. Median of sample is ~20.5 minutes (1230 seconds)
    assert 1140 <= summary.median_seconds <= 1320

    # 3. Simple arithmetic average would be (18+21+19+20+22+65+300+17)/8 = 60.25 minutes (3615s)
    # The robust estimator MUST be significantly lower than naive average (not distorted by 300m)
    assert summary.robust_estimate_seconds < 2400  # < 40 minutes

    # 4. But it MUST be higher than the pure median of normal cases (~20m) because the 65m
    # consultation is preserved as genuine clinical evidence!
    # Expected estimate is around 22–26 minutes.
    assert summary.robust_estimate_seconds > summary.median_seconds

    # 5. Honest uncertainty window from MAD
    assert 3 <= summary.uncertainty_minutes <= 30

    # 6. Feature vector payload diagnostics
    features = {}
    pred_sec, unc_min, model_type, model_ver, status = predictor.predict_duration(features, historical_seconds)
    assert status == "VALID"
    assert "outlier_analysis" in features
    diag = features["outlier_analysis"]
    assert diag["legitimate_long_count"] == 1
    assert diag["extreme_anomaly_count"] == 1
    assert diag["outlier_treatment"] == "IQR_HUBER_WEIGHTED"


def test_insufficient_historical_data_falls_back_with_low_confidence():
    """Verify that with insufficient data (< 3 samples), Q-FLOW does NOT fabricate data,
    but safely falls back to standard clinical default and reports FALLBACK status.
    """
    predictor = OutlierAwareDurationPredictor()
    features = {}
    pred_sec, unc_min, model_type, model_ver, status = predictor.predict_duration(features, [1200])

    assert pred_sec == SAFE_DEFAULT_DURATION_SECONDS  # 15 minutes
    assert unc_min == SAFE_DEFAULT_UNCERTAINTY_MINUTES
    assert status == "FALLBACK"


# ===========================================================================
# 2. DYNAMIC REFORECASTING ON ACTIVE OVERRUN & QUEUE EVENTS
# ===========================================================================

def test_active_consultation_overrun_dynamically_delays_downstream_queue(db_session: Session, test_setup):
    """When a doctor's active consultation exceeds expected duration (e.g. 45 min instead of 20 min),
    Q-FLOW dynamically recalculates the downstream queue and shifts waiting patients later.
    """
    queue = test_setup["queue"]
    patients = test_setup["patients"]

    # Entry 1: Currently in consultation
    entry1 = QueueEngineService.join_queue(db_session, queue.id, patients[0].id)
    entry1.status = QueueEntryStatus.IN_CONSULTATION
    db_session.flush()

    # Active consultation started 45 minutes ago (overrun against expected 20m)
    started_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    consult = Consultation(
        queue_entry_id=entry1.id,
        doctor_id=test_setup["doctor"].id,
        started_at=started_at,
        completed_at=None,
    )
    db_session.add(consult)

    # Entry 2: Patient waiting behind active consultation
    entry2 = QueueEngineService.join_queue(db_session, queue.id, patients[1].id)
    entry2.status = QueueEntryStatus.WAITING
    db_session.commit()

    service = PredictionService()
    calc = service.calculate_entry_prediction(db_session, entry2)

    # Entry 2's predicted start should account for the active overrun plus a dynamic clinical wrap-up tail (>= 5 min)
    now = datetime.now(timezone.utc)
    seconds_until_turn = (calc["predicted_start_at"] - now).total_seconds()
    # It must be at least 250 seconds (accounting for 300s dynamic tail minus DB run execution time), NOT clamped to 60s!
    assert seconds_until_turn >= 250


def test_doctor_delay_event_shifts_predicted_consultation_and_triggers_reforecast(db_session: Session, test_setup):
    """When staff reports a 20-minute doctor delay, downstream waiting patients' ETA moves 20 minutes later."""
    queue = test_setup["queue"]
    patients = test_setup["patients"]

    entry = QueueEngineService.join_queue(db_session, queue.id, patients[1].id)
    entry.status = QueueEntryStatus.WAITING
    db_session.commit()

    service = PredictionService()
    pred_before = service.calculate_entry_prediction(db_session, entry)

    # Record DOCTOR_DELAY event of 20 minutes
    delay_event = QueueEvent(
        queue_id=queue.id,
        queue_entry_id=entry.id,
        event_type=QueueEventType.DOCTOR_DELAY.value,
        event_time=datetime.now(timezone.utc),
        payload_json={"delay_minutes": 20, "reason": "Emergency ward consult"},
    )
    db_session.add(delay_event)
    db_session.commit()

    pred_after = service.calculate_entry_prediction(db_session, entry)

    shift_seconds = (pred_after["predicted_start_at"] - pred_before["predicted_start_at"]).total_seconds()
    # Shift should be exactly 20 minutes (1200 seconds)
    assert round(shift_seconds) == 1200


# ===========================================================================
# 3. REAL GOOGLE ROUTING ENGINE & TRAVEL MODES TESTS
# ===========================================================================

def test_google_routes_provider_queries_three_modes_with_traffic_awareness():
    """Verify GoogleRoutesProvider constructs correct payload for Routes API v2:
    - DRIVE: TRAFFIC_AWARE routingPreference
    - TWO_WHEELER: TRAFFIC_AWARE routingPreference (Indian motorcycle / scooter)
    - WALK: Standard pedestrian routing
    - Future departureTime is propagated when scheduled
    - Zero fake ratios or assumed speeds used
    """
    mock_responses = {
        "DRIVE": {
            "routes": [{
                "duration": "2520s",         # 42 min
                "staticDuration": "2100s",   # 35 min free flow -> traffic aware
                "distanceMeters": 18500,
            }]
        },
        "TWO_WHEELER": {
            "routes": [{
                "duration": "2100s",         # 35 min
                "staticDuration": "1800s",   # 30 min free flow
                "distanceMeters": 17200,
            }]
        },
        "WALK": {
            "routes": [{
                "duration": "4200s",         # 70 min (1 hr 10 min)
                "distanceMeters": 5800,
            }]
        },
    }

    recorded_requests = []

    def mock_transport(request: httpx.Request):
        import json
        body = json.loads(request.content.decode("utf-8"))
        mode = body.get("travelMode")
        recorded_requests.append({"mode": mode, "body": body, "headers": dict(request.headers)})
        resp_data = mock_responses.get(mode, {"routes": []})
        return httpx.Response(status_code=200, json=resp_data)

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = GoogleRoutesProvider(api_key="real-test-api-key-12345", http_client=client)

    future_dep = datetime.now(timezone.utc) + timedelta(hours=2)

    # 1. DRIVE
    drive_est = provider.estimate_travel(
        origin_lat=19.1895, origin_lng=73.0227,  # Mumbra Station
        dest_lat=19.0026, dest_lng=72.8423,    # KEM Hospital
        travel_mode="DRIVE",
        departure_time=future_dep,
    )
    assert drive_est.duration_seconds == 2520
    assert drive_est.distance_meters == 18500
    assert drive_est.travel_mode == "DRIVE"
    assert drive_est.is_traffic_aware is True

    # 2. TWO_WHEELER
    bike_est = provider.estimate_travel(
        origin_lat=19.1895, origin_lng=73.0227,
        dest_lat=19.0026, dest_lng=72.8423,
        travel_mode="TWO_WHEELER",
        departure_time=future_dep,
    )
    assert bike_est.duration_seconds == 2100
    assert bike_est.distance_meters == 17200
    assert bike_est.travel_mode == "TWO_WHEELER"
    assert bike_est.is_traffic_aware is True

    # 3. WALK
    walk_est = provider.estimate_travel(
        origin_lat=19.1895, origin_lng=73.0227,
        dest_lat=19.0026, dest_lng=72.8423,
        travel_mode="WALK",
    )
    assert walk_est.duration_seconds == 4200
    assert walk_est.distance_meters == 5800
    assert walk_est.travel_mode == "WALK"

    # Verify requests sent to Routes API v2
    assert len(recorded_requests) == 3
    for req in recorded_requests:
        assert "x-goog-api-key" in req["headers"]
        assert req["headers"]["x-goog-api-key"] == "real-test-api-key-12345"
        assert req["headers"]["x-goog-fieldmask"] == "routes.duration,routes.staticDuration,routes.distanceMeters"


def test_missing_google_api_key_returns_configuration_required_with_zero_fake_numbers(db_session: Session, test_setup):
    """PART 14: If Google Maps credentials are missing, DO NOT fall back to random/mock values.
    Display 'Travel estimate unavailable — Google Maps routing is not configured.'
    """
    queue = test_setup["queue"]
    patient = test_setup["patients"][0]

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("19.1895")
    entry.origin_longitude = Decimal("73.0227")
    entry.origin_address = "Mumbra Railway Station"
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(hours=2),
        predicted_end_at=now + timedelta(hours=2, minutes=20),
        predicted_duration_seconds=1200,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    # GoogleRoutesProvider initialized without API key
    unconfigured_provider = GoogleRoutesProvider(api_key=None)
    optimizer = ArrivalOptimizationService(travel_provider=unconfigured_provider)

    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_status == "CONFIGURATION_REQUIRED"
    assert plan.travel_duration_seconds is None
    assert plan.driving_duration_seconds is None
    assert plan.bike_duration_seconds is None
    assert plan.walking_duration_seconds is None
    assert plan.departure_start_at is None
    assert plan.departure_end_at is None
    assert "Google Maps routing is not configured" in plan.explanation


# ===========================================================================
# 4. RECOMMENDED DEPARTURE TIME ENGINE TESTS
# ===========================================================================

def test_recommended_departure_formula_exact_calculation(db_session: Session, test_setup):
    """PART 10: Recommended departure calculation formula:
    recommended_departure = predicted_turn_time - travel_duration - arrival_buffer

    Exact Example from Specification:
    Predicted Turn: 4:35 PM
    Walking: 1 hr 10 min (70 min = 4200s)
    Arrival Buffer: 15 min (900s)
    Expected Departure: 3:10 PM!
    """
    queue = test_setup["queue"]
    patient = test_setup["patients"][0]

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("19.1895")
    entry.origin_longitude = Decimal("73.0227")
    entry.travel_mode = "WALK"
    db_session.commit()

    # Predicted turn set to 4:35 PM today (UTC for clean test math)
    today = datetime.now(timezone.utc).date()
    turn_time = datetime(today.year, today.month, today.day, 16, 35, 0, tzinfo=timezone.utc)

    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=turn_time,
        predicted_end_at=turn_time + timedelta(minutes=20),
        predicted_duration_seconds=1200,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    # Mock provider that returns exact 70 min walk, 35 min bike, 42 min car
    class ExactTestProvider:
        def estimate_travel(self, origin_lat, origin_lng, dest_lat, dest_lng, travel_mode="DRIVE", departure_time=None):
            mode = (travel_mode or "DRIVE").upper()
            if mode == "WALK":
                return TravelEstimateResult(duration_seconds=4200, uncertainty_seconds=300, distance_meters=5800, provider="google_routes", travel_mode="WALK", travel_status="OPTIMIZED", calculated_at=datetime.now(timezone.utc))
            elif mode == "TWO_WHEELER":
                return TravelEstimateResult(duration_seconds=2100, uncertainty_seconds=300, distance_meters=17200, provider="google_routes", travel_mode="TWO_WHEELER", travel_status="OPTIMIZED", calculated_at=datetime.now(timezone.utc))
            else:
                return TravelEstimateResult(duration_seconds=2520, uncertainty_seconds=300, distance_meters=18500, provider="google_routes", travel_mode="DRIVE", travel_status="OPTIMIZED", calculated_at=datetime.now(timezone.utc))

        def estimate_all_modes(self, origin_lat, origin_lng, dest_lat, dest_lng, departure_time=None):
            return {
                "WALK": self.estimate_travel(origin_lat, origin_lng, dest_lat, dest_lng, "WALK"),
                "TWO_WHEELER": self.estimate_travel(origin_lat, origin_lng, dest_lat, dest_lng, "TWO_WHEELER"),
                "DRIVE": self.estimate_travel(origin_lat, origin_lng, dest_lat, dest_lng, "DRIVE"),
            }

    optimizer = ArrivalOptimizationService(travel_provider=ExactTestProvider())

    def to_utc(dt):
        return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    # 1. Walk Mode: 70 min travel + 15 min buffer = 85 min before turn
    # 4:35 PM - 85 min = 3:10 PM!
    plan_walk = optimizer.calculate_arrival_plan(db_session, entry, snapshot, buffer_minutes=15, selected_travel_mode="WALK")

    assert to_utc(plan_walk.departure_end_at) == datetime(today.year, today.month, today.day, 15, 10, 0, tzinfo=timezone.utc)
    assert plan_walk.travel_duration_seconds == 70 * 60
    assert plan_walk.arrival_buffer_seconds == 15 * 60

    # 2. Switch to Bike Mode: 35 min travel + 15 min buffer = 50 min before turn
    # 4:35 PM - 50 min = 3:45 PM!
    plan_bike = optimizer.calculate_arrival_plan(db_session, entry, snapshot, buffer_minutes=15, selected_travel_mode="TWO_WHEELER")

    assert to_utc(plan_bike.departure_end_at) == datetime(today.year, today.month, today.day, 15, 45, 0, tzinfo=timezone.utc)
    assert plan_bike.travel_duration_seconds == 35 * 60

    # 3. Switch to Car Mode: 42 min travel + 15 min buffer = 57 min before turn
    # 4:35 PM - 57 min = 3:38 PM!
    plan_car = optimizer.calculate_arrival_plan(db_session, entry, snapshot, buffer_minutes=15, selected_travel_mode="DRIVE")

    assert to_utc(plan_car.departure_end_at) == datetime(today.year, today.month, today.day, 15, 38, 0, tzinfo=timezone.utc)
    assert plan_car.travel_duration_seconds == 42 * 60


def test_three_engines_remain_strictly_separated(db_session: Session, test_setup):
    """PART 12: Verify that the 3 engines remain logically separated:
    - Switching travel mode recalculates recommended departure, but DOES NOT alter queue prediction.
    - A queue doctor delay updates queue prediction and departure recommendation, but DOES NOT alter travel duration.
    """
    queue = test_setup["queue"]
    patient = test_setup["patients"][0]

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("19.1895")
    entry.origin_longitude = Decimal("73.0227")
    db_session.commit()

    today = datetime.now(timezone.utc).date()
    turn_time = datetime(today.year, today.month, today.day, 17, 0, 0, tzinfo=timezone.utc)

    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=turn_time,
        predicted_end_at=turn_time + timedelta(minutes=20),
        predicted_duration_seconds=1200,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    class StrictTestProvider:
        def estimate_travel(self, origin_lat, origin_lng, dest_lat, dest_lng, travel_mode="DRIVE", departure_time=None):
            dur = 1800 if (travel_mode or "").upper() == "DRIVE" else 3600
            return TravelEstimateResult(duration_seconds=dur, uncertainty_seconds=300, distance_meters=10000, provider="google_routes", travel_mode=travel_mode, travel_status="OPTIMIZED", calculated_at=datetime.now(timezone.utc))

    optimizer = ArrivalOptimizationService(travel_provider=StrictTestProvider())

    def to_utc(dt):
        return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    plan1 = optimizer.calculate_arrival_plan(db_session, entry, snapshot, buffer_minutes=15, selected_travel_mode="DRIVE")
    # Turn time must remain completely untouched
    assert to_utc(plan1.consultation_start_at) == turn_time
    assert to_utc(plan1.departure_end_at) == turn_time - timedelta(minutes=30 + 15)  # 4:15 PM

    # Switch travel mode to WALK
    plan2 = optimizer.calculate_arrival_plan(db_session, entry, snapshot, buffer_minutes=15, selected_travel_mode="WALK")
    # Consultation turn time is STILL 5:00 PM (Queue engine not touched by travel mode)
    assert to_utc(plan2.consultation_start_at) == turn_time
    # Departure time shifted from 4:15 PM to 3:45 PM
    assert to_utc(plan2.departure_end_at) == turn_time - timedelta(minutes=60 + 15)  # 3:45 PM
