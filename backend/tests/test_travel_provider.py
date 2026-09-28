"""Unit tests for BaseTravelProvider, MockTravelProvider, GoogleRoutesProvider, and TravelCache."""

import time
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from app.services.travel.mock_provider import MockTravelProvider
from app.services.travel.google_routes_provider import GoogleRoutesProvider
from app.services.travel.cache import TravelCache
from app.services.travel.base import TravelProviderException


def test_mock_travel_provider_deterministic_estimates():
    """Verify MockTravelProvider returns deterministic, configurable durations and uncertainties."""
    provider = MockTravelProvider(
        default_duration_seconds=1500,
        default_uncertainty_seconds=240,
        default_distance_meters=10000,
        is_traffic_aware=True,
    )
    result = provider.estimate_travel(
        origin_lat=12.9352,
        origin_lng=77.6245,
        dest_lat=12.9716,
        dest_lng=77.5946,
        travel_mode="DRIVE",
    )

    assert result.duration_seconds == 1500
    assert result.uncertainty_seconds == 240
    assert result.distance_meters == 10000
    assert result.provider == "mock"
    assert result.travel_status in ("OPTIMIZED", "AVAILABLE")
    assert result.is_traffic_aware is True


def test_mock_travel_provider_simulated_failure():
    """Verify MockTravelProvider raises TravelProviderException when configured to fail."""
    provider = MockTravelProvider(should_fail=True)
    with pytest.raises(TravelProviderException) as exc:
        provider.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert "simulate failure" in str(exc.value).lower()
    assert exc.value.provider == "mock"



def test_google_routes_provider_missing_api_key():
    """Verify GoogleRoutesProvider raises TravelProviderException if API key is missing or empty."""
    provider = GoogleRoutesProvider(api_key="")
    with pytest.raises(TravelProviderException) as exc:
        provider.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert "not configured" in str(exc.value).lower()
    assert exc.value.provider == "google_routes"


def test_google_routes_provider_successful_mocked_response():
    """Verify GoogleRoutesProvider parses duration, staticDuration, and traffic uncertainty correctly."""
    mock_response_json = {
        "routes": [
            {
                "duration": "1800s",
                "staticDuration": "1500s",
                "distanceMeters": 14200,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Goog-Api-Key") == "test-api-key"
        return httpx.Response(200, json=mock_response_json)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GoogleRoutesProvider(api_key="test-api-key", http_client=client)

    result = provider.estimate_travel(12.935, 77.624, 12.971, 77.594, travel_mode="DRIVE")
    assert result.duration_seconds == 1800
    assert result.distance_meters == 14200
    assert result.provider == "google_routes"
    assert result.travel_status == "OPTIMIZED"
    assert result.is_traffic_aware is True
    # Traffic delta = |1800 - 1500| = 300s -> uncertainty is 300s
    assert result.uncertainty_seconds == 300


def test_google_routes_provider_api_error_and_malformed_response():
    """Verify GoogleRoutesProvider raises TravelProviderException on HTTP errors or empty routes."""
    # HTTP 403 Forbidden
    def handler_403(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "Quota exceeded"})

    provider_403 = GoogleRoutesProvider(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler_403)))
    with pytest.raises(TravelProviderException) as exc:
        provider_403.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert exc.value.status_code == 403

    # Empty routes list
    def handler_empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"routes": []})

    provider_empty = GoogleRoutesProvider(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler_empty)))
    with pytest.raises(TravelProviderException) as exc:
        provider_empty.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert "no routes" in str(exc.value).lower()


def test_google_routes_provider_timeout():
    """Verify GoogleRoutesProvider raises TravelProviderException on network timeout."""
    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    provider_timeout = GoogleRoutesProvider(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler_timeout)))
    with pytest.raises(TravelProviderException) as exc:
        provider_timeout.estimate_travel(12.9, 77.6, 12.97, 77.59)
    assert "network error" in str(exc.value).lower()


def test_travel_cache_hit_and_ttl_expiration():
    """Verify TravelCache serves cached estimates and evicts on TTL expiry."""
    cache = TravelCache(ttl_seconds=1, time_bucket_seconds=60)
    provider = MockTravelProvider(default_duration_seconds=1200)

    est1 = provider.estimate_travel(12.9352, 77.6245, 12.9716, 77.5946)
    dep_time = datetime.now(timezone.utc)

    # Put in cache
    cache.set(12.9352, 77.6245, 12.9716, 77.5946, "DRIVE", dep_time, est1)

    # Immediate get -> Hit
    cached = cache.get(12.9352, 77.6245, 12.9716, 77.5946, "DRIVE", dep_time)
    assert cached is not None
    assert cached.duration_seconds == 1200

    # Wait for TTL expiry
    time.sleep(1.1)
    expired = cache.get(12.9352, 77.6245, 12.9716, 77.5946, "DRIVE", dep_time)
    assert expired is None
