"""In-memory thread-safe travel estimate cache with time-bucketing and TTL."""

import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from app.services.travel.base import TravelEstimateResult


class TravelCache:
    """Thread-safe time-bucketed cache for travel duration estimates."""

    def __init__(self, ttl_seconds: int = 600, time_bucket_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.time_bucket_seconds = time_bucket_seconds
        self._lock = threading.Lock()
        # Storage: key -> (TravelEstimateResult, insertion_timestamp)
        self._store: Dict[str, Tuple[TravelEstimateResult, float]] = {}

    def _build_key(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str,
        departure_time: Optional[datetime],
    ) -> str:
        """Construct deterministic cache key rounding coordinates to ~11 meters and bucketing time."""
        o_lat = round(origin_lat, 4)
        o_lng = round(origin_lng, 4)
        d_lat = round(dest_lat, 4)
        d_lng = round(dest_lng, 4)

        if departure_time:
            epoch = departure_time.astimezone(timezone.utc).timestamp()
            bucket = int(epoch // self.time_bucket_seconds)
        else:
            # If no departure time, bucket current UTC time
            epoch = datetime.now(timezone.utc).timestamp()
            bucket = int(epoch // self.time_bucket_seconds)

        return f"{o_lat},{o_lng}->{d_lat},{d_lng}:{travel_mode}:{bucket}"

    def get(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str,
        departure_time: Optional[datetime],
    ) -> Optional[TravelEstimateResult]:
        """Retrieve cached estimate if present and not expired."""
        key = self._build_key(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode, departure_time)
        now_ts = datetime.now(timezone.utc).timestamp()

        with self._lock:
            if key in self._store:
                result, inserted_at = self._store[key]
                if now_ts - inserted_at <= self.ttl_seconds:
                    return result
                # Expired
                del self._store[key]
        return None

    def set(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str,
        departure_time: Optional[datetime],
        estimate: TravelEstimateResult,
    ) -> None:
        """Store travel estimate in cache."""
        key = self._build_key(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode, departure_time)
        now_ts = datetime.now(timezone.utc).timestamp()

        with self._lock:
            # Optional cleanup if store grows large
            if len(self._store) > 2000:
                expired = [k for k, (_, ts) in self._store.items() if now_ts - ts > self.ttl_seconds]
                for k in expired:
                    del self._store[k]
            self._store[key] = (estimate, now_ts)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()
