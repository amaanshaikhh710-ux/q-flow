"""Deterministic mock travel provider for local development and unit testing."""

from datetime import datetime, timezone
from typing import Optional
from app.services.travel.base import BaseTravelProvider, TravelEstimateResult, TravelProviderException


class MockTravelProvider(BaseTravelProvider):
    """Deterministic, configurable mock provider for transit times."""

    def __init__(
        self,
        default_duration_seconds: int = 1800,       # 30 minutes
        default_uncertainty_seconds: int = 300,     # 5 minutes
        default_distance_meters: int = 12000,       # 12 km
        travel_status: str = "OPTIMIZED",
        is_traffic_aware: bool = False,
        should_fail: bool = False,
        is_degraded: bool = False,
    ):
        self.default_duration_seconds = default_duration_seconds
        self.default_uncertainty_seconds = default_uncertainty_seconds
        self.default_distance_meters = default_distance_meters
        self.travel_status = "DEGRADED" if is_degraded else travel_status
        self.is_traffic_aware = is_traffic_aware
        self.should_fail = should_fail
        self.is_degraded = is_degraded

    def estimate_travel(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        departure_time: Optional[datetime] = None,
    ) -> TravelEstimateResult:
        """Return deterministic travel estimates or simulate configured failure."""
        if self.should_fail:
            raise TravelProviderException("Mock travel provider configured to simulate failure", provider="mock")

        duration = self.default_duration_seconds
        uncertainty = self.default_uncertainty_seconds
        if travel_mode.upper() == "WALK":
            # Walking is ~2.5x driving duration, with smaller uncertainty (~180s)
            duration = int(self.default_duration_seconds * 2.5)
            uncertainty = max(180, int(self.default_uncertainty_seconds * 0.6))

        return TravelEstimateResult(
            duration_seconds=duration,
            uncertainty_seconds=uncertainty,
            distance_meters=self.default_distance_meters,
            provider="mock",
            travel_status=self.travel_status,
            is_traffic_aware=self.is_traffic_aware,
            calculated_at=datetime.now(timezone.utc),
        )
