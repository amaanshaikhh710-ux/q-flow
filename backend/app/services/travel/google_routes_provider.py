"""Google Routes API v2 integration for real-world transit duration estimation."""

import logging
from datetime import datetime, timezone
from typing import Optional, Any
import httpx

from app.services.travel.base import BaseTravelProvider, TravelEstimateResult, TravelProviderException

logger = logging.getLogger(__name__)

ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
DEFAULT_TIMEOUT_SECONDS = 10.0


class GoogleRoutesProvider(BaseTravelProvider):
    """Google Routes API v2 provider."""

    def __init__(self, api_key: Optional[str] = None, http_client: Optional[httpx.Client] = None):
        self.api_key = api_key
        self._client = http_client

    def _parse_duration_string(self, duration_str: str) -> int:
        """Parse Google Routes API duration format (e.g., '1540s' -> 1540)."""
        if not duration_str:
            return 0
        cleaned = duration_str.strip().rstrip("s")
        return int(float(cleaned))

    def estimate_travel(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        departure_time: Optional[datetime] = None,
    ) -> TravelEstimateResult:
        """Query Google Routes API for transit duration and traffic-aware variance."""
        if not self.api_key or not self.api_key.strip():
            raise TravelProviderException("Google Routes API key is not configured or is empty", provider="google_routes")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
        }

        mode_upper = (travel_mode or "DRIVE").upper()
        if mode_upper in ("BIKE", "TWO_WHEELER", "MOTORCYCLE"):
            normalized_mode = "TWO_WHEELER"
        elif mode_upper in ("WALK", "WALKING"):
            normalized_mode = "WALK"
        elif mode_upper in ("TRANSIT", "BUS", "TRAIN"):
            normalized_mode = "TRANSIT"
        else:
            normalized_mode = "DRIVE"

        payload: dict[str, Any] = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": float(origin_lat),
                        "longitude": float(origin_lng),
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": float(dest_lat),
                        "longitude": float(dest_lng),
                    }
                }
            },
            "travelMode": normalized_mode,
        }

        if normalized_mode in ("DRIVE", "TWO_WHEELER"):
            payload["routingPreference"] = "TRAFFIC_AWARE"

        if departure_time:
            payload["departureTime"] = departure_time.astimezone(timezone.utc).isoformat()

        try:
            if self._client:
                response = self._client.post(ROUTES_API_URL, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
            else:
                with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                    response = client.post(ROUTES_API_URL, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error("Google Routes API HTTP error: %d", response.status_code)
                raise TravelProviderException(
                    f"Google Routes API returned HTTP {response.status_code}",
                    provider="google_routes",
                    status_code=response.status_code,
                )

            data = response.json()
            routes = data.get("routes", [])
            if not routes:
                raise TravelProviderException("Google Routes API returned no routes for coordinates", provider="google_routes")

            primary_route = routes[0]
            duration_seconds = self._parse_duration_string(primary_route.get("duration", "0s"))
            static_duration_seconds = self._parse_duration_string(primary_route.get("staticDuration", "0s"))
            distance_meters = primary_route.get("distanceMeters")

            # Traffic-aware uncertainty: difference between current live traffic and free-flow static duration
            traffic_delta = abs(duration_seconds - static_duration_seconds) if static_duration_seconds else 0
            # Bound uncertainty to minimum 300s (5 mins), max 3600s (60 mins)
            uncertainty_seconds = max(300, min(3600, traffic_delta))

            return TravelEstimateResult(
                duration_seconds=duration_seconds,
                uncertainty_seconds=uncertainty_seconds,
                distance_meters=distance_meters,
                provider="google_routes",
                travel_mode=normalized_mode,
                travel_status="OPTIMIZED",
                is_traffic_aware=bool(static_duration_seconds and static_duration_seconds != duration_seconds),
                calculated_at=datetime.now(timezone.utc),
            )

        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error("Google Routes API network failure: %s", e)
            raise TravelProviderException(f"Network error communicating with Google Routes API: {e}", provider="google_routes")
        except ValueError as e:
            logger.error("Failed to parse Google Routes API response: %s", e)
            raise TravelProviderException(f"Invalid response payload from Google Routes API: {e}", provider="google_routes")

    def estimate_all_modes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        departure_time: Optional[datetime] = None,
    ) -> dict[str, Optional[TravelEstimateResult]]:
        """Calculate routes for all 3 supported Google Routes API modes: DRIVE (Car), TWO_WHEELER (Bike), and WALK."""
        results: dict[str, Optional[TravelEstimateResult]] = {}
        for mode in ("DRIVE", "TWO_WHEELER", "WALK"):
            try:
                results[mode] = self.estimate_travel(
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    dest_lat=dest_lat,
                    dest_lng=dest_lng,
                    travel_mode=mode,
                    departure_time=departure_time,
                )
            except Exception as e:
                logger.warning("Could not calculate travel for mode %s: %s", mode, e)
                results[mode] = None
        return results

