"""Phase 5.1 hardening tests for Google Routes failure handling, canonical API key, and arrival plan transparency."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from app.core.config import settings
from app.models.user import UserRole
from app.models.queue_entry import QueueEntry
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.services.travel import get_travel_provider, travel_cache
from app.services.travel.base import TravelProviderException
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.travel.mock_provider import MockTravelProvider
from app.services.arrival_optimizer import ArrivalOptimizationService
from app.services.queue_engine import QueueEngineService
from tests.conftest import make_test_user


@pytest.fixture(autouse=True)
def clear_travel_cache_fixture():
    travel_cache.clear()
    yield
    travel_cache.clear()


def test_google_routes_success_sets_optimized_status(db_session, seed_opd_data):
    """Requirement 4.1: Google success sets provider = google_routes and status = OPTIMIZED."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Google Success Pat", "googlesucc@test.com", UserRole.PATIENT)

    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    base_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=base_time,
        predicted_end_at=base_time + timedelta(minutes=20),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    # Mock successful HTTP 200 response from Google Routes v2
    def handler_200(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "duration": "1200s",
                        "staticDuration": "1000s",
                        "distanceMeters": 9500,
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler_200))
    provider = GoogleRoutesProvider(api_key="valid-test-key", http_client=client)

    # 1. Direct estimate verification
    est = provider.estimate_travel(12.9352, 77.6245, 12.9716, 77.5946)
    assert est.provider == "google_routes"
    assert est.travel_status == "OPTIMIZED"
    assert est.duration_seconds == 1200

    # 2. Arrival plan calculation verification
    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_provider == "google_routes"
    assert plan.travel_status == "OPTIMIZED"
    assert plan.travel_duration_seconds == 1200
    assert "live traffic conditions" in plan.explanation


def test_no_api_key_in_local_test_uses_mock_provider(monkeypatch, db_session, seed_opd_data):
    """Requirement 4.2: No API key in local/test uses provider = mock with development explanation."""
    monkeypatch.setattr(settings, "GOOGLE_ROUTES_API_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", None)

    # Resolver check
    provider = get_travel_provider()
    assert isinstance(provider, MockTravelProvider)

    # Estimate check
    est = provider.estimate_travel(12.9352, 77.6245, 12.9716, 77.5946)
    assert est.provider == "mock"

    # Arrival plan check
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Dev Mock Pat", "devmock@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=50),
        predicted_end_at=now + timedelta(minutes=70),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_provider == "mock"
    assert "Development travel estimate" in plan.explanation


def test_configured_google_api_failure_returns_degraded_status(db_session, seed_opd_data):
    """Requirement 4.3: Configured Google API failure returns provider != google_routes and status != OPTIMIZED."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Google Fail Pat", "googlefail@test.com", UserRole.PATIENT)
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
    )
    db_session.add(snapshot)
    db_session.commit()

    # Google API returns 403 Forbidden (e.g. quota exceeded or billing issue)
    def handler_403(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "Daily quota exceeded"})

    client = httpx.Client(transport=httpx.MockTransport(handler_403))
    provider = GoogleRoutesProvider(api_key="configured-key", http_client=client)

    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    # Invariants: NEVER claim google_routes, NEVER claim OPTIMIZED
    assert plan.travel_provider != "google_routes"
    assert plan.travel_status != "OPTIMIZED"
    assert plan.travel_status == "DEGRADED"
    assert plan.travel_provider == "mock"
    assert "temporarily unavailable" in plan.explanation
    assert "consultation estimate is still available" in plan.explanation


def test_timeout_no_false_google_success(db_session, seed_opd_data):
    """Requirement 4.4: Network timeout does not produce false Google success."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Timeout Pat", "timeoutpat@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=50),
        predicted_end_at=now + timedelta(minutes=70),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out after 10.0s")

    client = httpx.Client(transport=httpx.MockTransport(handler_timeout))
    provider = GoogleRoutesProvider(api_key="configured-key", http_client=client)

    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_provider != "google_routes"
    assert plan.travel_status != "OPTIMIZED"
    assert plan.travel_status == "DEGRADED"
    assert "temporarily unavailable" in plan.explanation


def test_500_error_no_false_google_success(db_session, seed_opd_data):
    """Requirement 4.5: Google 500 error does not produce false Google success."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "500 Pat", "err500pat@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=50),
        predicted_end_at=now + timedelta(minutes=70),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    def handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(handler_500))
    provider = GoogleRoutesProvider(api_key="configured-key", http_client=client)

    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_provider != "google_routes"
    assert plan.travel_status != "OPTIMIZED"
    assert plan.travel_status == "DEGRADED"


def test_malformed_response_no_false_google_success(db_session, seed_opd_data):
    """Requirement 4.6: Malformed response or empty routes list does not produce false Google success."""
    queue = seed_opd_data["queue"]
    patient, _ = make_test_user(db_session, "Malformed Pat", "malformed@test.com", UserRole.PATIENT)
    entry = QueueEngineService.join_queue(db_session, queue.id, patient.id)
    entry.origin_latitude = Decimal("12.9352")
    entry.origin_longitude = Decimal("77.6245")
    db_session.commit()

    now = datetime.now(timezone.utc)
    snapshot = PredictionSnapshot(
        queue_entry_id=entry.id,
        queue_id=queue.id,
        predicted_start_at=now + timedelta(minutes=50),
        predicted_end_at=now + timedelta(minutes=70),
        predicted_duration_seconds=900,
        uncertainty_minutes=5,
    )
    db_session.add(snapshot)
    db_session.commit()

    # Empty routes list
    def handler_empty_routes(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"routes": []})

    client = httpx.Client(transport=httpx.MockTransport(handler_empty_routes))
    provider = GoogleRoutesProvider(api_key="configured-key", http_client=client)

    optimizer = ArrivalOptimizationService(travel_provider=provider)
    plan = optimizer.calculate_arrival_plan(db_session, entry, snapshot)

    assert plan.travel_provider != "google_routes"
    assert plan.travel_status != "OPTIMIZED"
    assert plan.travel_status == "DEGRADED"


def test_missing_and_placeholder_api_key_behavior(monkeypatch):
    """Requirement 4.7: Missing or placeholder API key correctly resolves to Mock provider."""
    # Empty string
    monkeypatch.setattr(settings, "GOOGLE_ROUTES_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")
    p1 = get_travel_provider()
    assert isinstance(p1, MockTravelProvider)

    # Placeholder string
    monkeypatch.setattr(settings, "GOOGLE_ROUTES_API_KEY", "your-google-routes-api-key")
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", None)
    p2 = get_travel_provider()
    assert isinstance(p2, MockTravelProvider)

    # Direct instantiation with empty key raises TravelProviderException
    direct = GoogleRoutesProvider(api_key="")
    with pytest.raises(TravelProviderException) as exc:
        direct.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert "Google Routes API key is not configured" in exc.value.message


def test_api_response_never_exposes_api_key(test_client, db_session, seed_opd_data, monkeypatch):
    """Requirement 4.8: API responses and payloads never expose Google API keys."""
    canary_key = "SUPER-SECRET-CANARY-KEY-ABC123XYZ"
    monkeypatch.setattr(settings, "GOOGLE_ROUTES_API_KEY", canary_key)

    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Canary Pat", "canary@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    # 1. Post origin
    origin_res = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/travel-origin",
        json={"latitude": 12.9352, "longitude": 77.6245, "travel_mode": "DRIVE"},
        headers=p_headers,
    )
    assert canary_key not in origin_res.text

    # 2. Get travel estimate
    travel_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/travel", headers=p_headers)
    assert canary_key not in travel_res.text

    # 3. Get arrival plan
    plan_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/arrival-plan", headers=p_headers)
    assert canary_key not in plan_res.text

    # 4. Get history
    hist_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/arrival-plan/history", headers=p_headers)
    assert canary_key not in hist_res.text
