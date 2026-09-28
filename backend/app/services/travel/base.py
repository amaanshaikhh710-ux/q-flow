"""Base abstractions and data structures for travel estimation providers."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class TravelEstimateResult(BaseModel):
    """Encapsulates the result of a travel-time calculation."""
    duration_seconds: int = Field(..., ge=0, description="Transit duration in seconds")
    uncertainty_seconds: int = Field(..., ge=0, description="Transit uncertainty margin in seconds")
    distance_meters: Optional[int] = Field(None, ge=0, description="Route distance in meters")
    provider: str = Field(..., description="Provider identifier (e.g. mock, google_routes)")
    travel_mode: str = Field("DRIVE", description="Travel mode used for this estimate (DRIVE, TWO_WHEELER, WALK)")
    travel_status: str = Field("OPTIMIZED", description="OPTIMIZED, DEGRADED, or UNAVAILABLE")
    is_traffic_aware: bool = Field(False, description="Whether live traffic conditions were factored")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TravelProviderException(Exception):
    """Raised when an external travel provider fails or returns unparseable data."""
    def __init__(self, message: str, provider: str = "unknown", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class BaseTravelProvider(ABC):
    """Abstract interface for transit duration and uncertainty providers."""

    @abstractmethod
    def estimate_travel(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
        departure_time: Optional[datetime] = None,
    ) -> TravelEstimateResult:
        """Calculate transit duration and uncertainty between origin and destination."""
        pass
