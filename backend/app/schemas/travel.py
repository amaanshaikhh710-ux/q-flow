"""Pydantic schemas for Travel Origin, Estimates, and Arrival/Departure Optimization Plans."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TravelOriginRequest(BaseModel):
    """Payload for patient to configure or update their starting location."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Origin latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Origin longitude in decimal degrees (-180 to 180)")
    travel_mode: str = Field(
        "DRIVE",
        pattern="^(DRIVE|TRANSIT|WALK|TWO_WHEELER)$",
        description="Mode of travel: DRIVE, TRANSIT, WALK, TWO_WHEELER",
    )
    origin_address: Optional[str] = Field(None, max_length=255, description="Human-readable origin address or landmark")


class TravelModeUpdateRequest(BaseModel):
    """Payload to switch active travel mode (DRIVE, TWO_WHEELER, WALK)."""
    travel_mode: str = Field(..., pattern="^(DRIVE|TWO_WHEELER|WALK)$", description="Selected travel mode: DRIVE, TWO_WHEELER, WALK")


class TravelEstimateResponse(BaseModel):
    """Travel duration and uncertainty estimate from travel provider."""
    travel_duration_seconds: Optional[int] = Field(None, ge=0, description="Estimated transit duration in seconds")
    travel_duration_minutes: Optional[int] = Field(None, ge=0, description="Estimated transit duration in minutes")
    travel_uncertainty_seconds: Optional[int] = Field(None, ge=0, description="Transit uncertainty margin in seconds")
    travel_uncertainty_minutes: Optional[int] = Field(None, ge=0, description="Transit uncertainty margin in minutes")
    route_distance_meters: Optional[int] = Field(None, ge=0, description="Transit distance in meters")
    driving_duration_seconds: Optional[int] = Field(None, ge=0, description="Driving transit duration in seconds")
    driving_duration_minutes: Optional[int] = Field(None, ge=0, description="Driving transit duration in minutes")
    driving_distance_meters: Optional[int] = Field(None, ge=0, description="Driving distance in meters")
    bike_duration_seconds: Optional[int] = Field(None, ge=0, description="Bike transit duration in seconds")
    bike_duration_minutes: Optional[int] = Field(None, ge=0, description="Bike transit duration in minutes")
    bike_distance_meters: Optional[int] = Field(None, ge=0, description="Bike distance in meters")
    walking_duration_seconds: Optional[int] = Field(None, ge=0, description="Walking transit duration in seconds")
    walking_duration_minutes: Optional[int] = Field(None, ge=0, description="Walking transit duration in minutes")
    walking_distance_meters: Optional[int] = Field(None, ge=0, description="Walking distance in meters")
    provider: str = Field(..., description="Provider source: mock or google_routes")
    travel_status: str = Field(..., description="Status: AVAILABLE, UNAVAILABLE, or ERROR")
    is_traffic_aware: bool = Field(False, description="Whether estimate accounts for live traffic")
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArrivalPlanResponse(BaseModel):
    """Complete travel-aware arrival and departure recommendation."""
    id: uuid.UUID
    queue_entry_id: uuid.UUID
    prediction_snapshot_id: uuid.UUID
    travel_provider: str
    travel_status: str
    consultation_start_at: datetime
    consultation_end_at: datetime
    arrival_start_at: Optional[datetime] = None
    arrival_end_at: Optional[datetime] = None
    departure_start_at: Optional[datetime] = None
    departure_end_at: Optional[datetime] = None
    travel_duration_seconds: Optional[int] = None
    travel_duration_minutes: Optional[int] = None
    travel_uncertainty_seconds: Optional[int] = None
    travel_uncertainty_minutes: Optional[int] = None
    route_distance_meters: Optional[int] = None
    driving_duration_seconds: Optional[int] = None
    driving_duration_minutes: Optional[int] = None
    driving_distance_meters: Optional[int] = None
    bike_duration_seconds: Optional[int] = None
    bike_duration_minutes: Optional[int] = None
    bike_distance_meters: Optional[int] = None
    walking_duration_seconds: Optional[int] = None
    walking_duration_minutes: Optional[int] = None
    walking_distance_meters: Optional[int] = None
    selected_travel_mode: Optional[str] = "DRIVE"
    origin_address: Optional[str] = None
    arrival_buffer_minutes: int = 15
    is_meaningful_change: bool = False
    consultation_changed: bool = False
    travel_changed: bool = False
    explanation: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArrivalPlanHistoryResponse(BaseModel):
    """Chronological history of arrival plans for a queue entry."""
    queue_entry_id: uuid.UUID
    total_plans: int
    history: List[ArrivalPlanResponse]


class ResolveAddressRequest(BaseModel):
    """Payload to search and resolve a textual location/address."""
    query: str = Field(..., min_length=2, max_length=200, description="Area or address query (e.g. Mumbra, Thane West, Dadar)")


class ResolvedLocationItem(BaseModel):
    """A resolved geographic location item."""
    name: str
    formatted_address: str
    latitude: float
    longitude: float


class ResolveAddressResponse(BaseModel):
    """Response containing matched locations."""
    query: str
    results: List[ResolvedLocationItem] = []
    resolved_by: str = Field("local_directory", description="Source: google_geocoding or local_directory")

