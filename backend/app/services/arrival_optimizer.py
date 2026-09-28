"""Arrival optimization service — computes arrival and departure windows from consultation ETAs and transit times."""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.models.queue_entry import QueueEntry
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.models.hospital import Hospital
from app.services.travel import (
    BaseTravelProvider,
    TravelEstimateResult,
    TravelProviderException,
    MockTravelProvider,
    get_travel_provider,
    travel_cache,
)

logger = logging.getLogger(__name__)

MEANINGFUL_CHANGE_THRESHOLD_SECONDS = 600  # 10 minutes


class ArrivalOptimizationService:
    """Service to calculate and persist travel-aware arrival and departure recommendations."""

    def __init__(self, travel_provider: Optional[BaseTravelProvider] = None):
        self._provider = travel_provider

    @property
    def provider(self) -> BaseTravelProvider:
        if self._provider is None:
            return get_travel_provider()
        return self._provider

    def _get_hospital_coordinates(self, db: Session, entry: QueueEntry) -> Tuple[float, float]:
        """Fetch hospital latitude and longitude for the queue entry."""
        queue = entry.queue
        hospital: Optional[Hospital] = None
        if queue and queue.opd_session and queue.opd_session.department:
            hospital = queue.opd_session.department.hospital

        if hospital and hospital.latitude is not None and hospital.longitude is not None:
            return float(hospital.latitude), float(hospital.longitude)

        # Safe clinic fallback coordinates (KEM Hospital, Parel, Mumbai)
        return 19.0026, 72.8423

    def compute_travel_estimate(
        self,
        entry: QueueEntry,
        hospital_lat: float,
        hospital_lng: float,
        departure_time: Optional[datetime] = None,
    ) -> Optional[TravelEstimateResult]:
        """Calculate transit time using cache and active provider."""
        if entry.origin_latitude is None or entry.origin_longitude is None:
            return None

        o_lat = float(entry.origin_latitude)
        o_lng = float(entry.origin_longitude)
        travel_mode = entry.travel_mode or "DRIVE"

        # Check cache
        cached = travel_cache.get(o_lat, o_lng, hospital_lat, hospital_lng, travel_mode, departure_time)
        if cached:
            return cached

        # Query provider
        estimate = self.provider.estimate_travel(
            origin_lat=o_lat,
            origin_lng=o_lng,
            dest_lat=hospital_lat,
            dest_lng=hospital_lng,
            travel_mode=travel_mode,
            departure_time=departure_time,
        )

        # Store in cache
        travel_cache.set(o_lat, o_lng, hospital_lat, hospital_lng, travel_mode, departure_time, estimate)
        return estimate

    def calculate_arrival_plan(
        self,
        db: Session,
        entry: QueueEntry,
        snapshot: PredictionSnapshot,
        buffer_minutes: int = settings.DEFAULT_ARRIVAL_BUFFER_MINUTES,
        selected_travel_mode: Optional[str] = None,
    ) -> ArrivalPlan:
        """Calculate and persist arrival and departure recommendations for a prediction snapshot."""
        now = datetime.now(timezone.utc)
        buffer_seconds = buffer_minutes * 60

        # Previous arrival plan for meaningful change tracking
        prev_plan = (
            db.query(ArrivalPlan)
            .filter(ArrivalPlan.queue_entry_id == entry.id)
            .order_by(desc(ArrivalPlan.created_at))
            .first()
        )

        consultation_start = snapshot.predicted_start_at
        consultation_end = snapshot.predicted_end_at

        # Determine selected travel mode
        selected_mode = (selected_travel_mode or entry.travel_mode or "DRIVE").upper()
        if selected_mode in ("BIKE", "MOTORCYCLE"):
            selected_mode = "TWO_WHEELER"
        elif selected_mode in ("WALKING",):
            selected_mode = "WALK"

        # Case 1: No travel origin provided by patient
        if entry.origin_latitude is None or entry.origin_longitude is None:
            plan = ArrivalPlan(
                queue_entry_id=entry.id,
                prediction_snapshot_id=snapshot.id,
                travel_provider=self.provider.__class__.__name__.lower().replace("provider", ""),
                travel_status="UNAVAILABLE",
                travel_duration_seconds=None,
                travel_uncertainty_seconds=None,
                route_distance_meters=None,
                driving_duration_seconds=None,
                driving_distance_meters=None,
                bike_duration_seconds=None,
                bike_distance_meters=None,
                walking_duration_seconds=None,
                walking_distance_meters=None,
                selected_travel_mode=selected_mode,
                arrival_buffer_seconds=buffer_seconds,
                consultation_start_at=consultation_start,
                consultation_end_at=consultation_end,
                arrival_start_at=None,
                arrival_end_at=None,
                departure_start_at=None,
                departure_end_at=None,
                is_meaningful_change=False,
                consultation_changed=False,
                travel_changed=False,
                explanation="Add your starting location to calculate a travel-aware departure recommendation.",
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            return plan

        # Case 2: Patient has configured starting location
        is_google = self.provider.__class__.__name__ == "GoogleRoutesProvider"
        api_key = getattr(self.provider, "api_key", None) or settings.canonical_google_routes_api_key
        if is_google and (not api_key or not api_key.strip() or api_key.startswith("your-google-")):
            plan = ArrivalPlan(
                queue_entry_id=entry.id,
                prediction_snapshot_id=snapshot.id,
                travel_provider="google_routes",
                travel_status="CONFIGURATION_REQUIRED",
                travel_duration_seconds=None,
                travel_uncertainty_seconds=None,
                route_distance_meters=None,
                driving_duration_seconds=None,
                driving_distance_meters=None,
                bike_duration_seconds=None,
                bike_distance_meters=None,
                walking_duration_seconds=None,
                walking_distance_meters=None,
                selected_travel_mode=selected_mode,
                arrival_buffer_seconds=buffer_seconds,
                consultation_start_at=consultation_start,
                consultation_end_at=consultation_end,
                arrival_start_at=None,
                arrival_end_at=None,
                departure_start_at=None,
                departure_end_at=None,
                is_meaningful_change=False,
                consultation_changed=False,
                travel_changed=False,
                explanation="Travel estimate unavailable — Google Maps routing is not configured.",
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            return plan

        h_lat, h_lng = self._get_hospital_coordinates(db, entry)

        # Arrival Window: buffer before predicted consultation start
        half_window = 300  # 5 minutes
        arrival_end = consultation_start - timedelta(seconds=half_window)
        arrival_start = consultation_start - timedelta(seconds=buffer_seconds + half_window)

        # Fetch transit estimates for all supported Google Routes modes (Car, Bike, Walk)
        driving_duration_seconds: Optional[int] = None
        driving_distance_meters: Optional[int] = None
        bike_duration_seconds: Optional[int] = None
        bike_distance_meters: Optional[int] = None
        walking_duration_seconds: Optional[int] = None
        walking_distance_meters: Optional[int] = None

        try:
            # 1. Drive (Car)
            try:
                drive_est = self.provider.estimate_travel(
                    origin_lat=float(entry.origin_latitude),
                    origin_lng=float(entry.origin_longitude),
                    dest_lat=h_lat,
                    dest_lng=h_lng,
                    travel_mode="DRIVE",
                    departure_time=arrival_start - timedelta(minutes=30),
                )
                if drive_est:
                    driving_duration_seconds = drive_est.duration_seconds
                    driving_distance_meters = drive_est.distance_meters
            except Exception as drive_err:
                logger.debug("Drive estimate failed: %s", drive_err)

            # 2. Two-Wheeler (Bike)
            try:
                bike_est = self.provider.estimate_travel(
                    origin_lat=float(entry.origin_latitude),
                    origin_lng=float(entry.origin_longitude),
                    dest_lat=h_lat,
                    dest_lng=h_lng,
                    travel_mode="TWO_WHEELER",
                    departure_time=arrival_start - timedelta(minutes=30),
                )
                if bike_est:
                    bike_duration_seconds = bike_est.duration_seconds
                    bike_distance_meters = bike_est.distance_meters
            except Exception as bike_err:
                logger.debug("Bike estimate failed: %s", bike_err)

            # 3. Walk
            try:
                walk_est = self.provider.estimate_travel(
                    origin_lat=float(entry.origin_latitude),
                    origin_lng=float(entry.origin_longitude),
                    dest_lat=h_lat,
                    dest_lng=h_lng,
                    travel_mode="WALK",
                )
                if walk_est:
                    walking_duration_seconds = walk_est.duration_seconds
                    walking_distance_meters = walk_est.distance_meters
            except Exception as walk_err:
                logger.debug("Walk estimate failed: %s", walk_err)

            # Determine active travel duration based on selected mode (NO silent substitution)
            if selected_mode == "TWO_WHEELER":
                travel_duration = bike_duration_seconds
                route_distance = bike_distance_meters
            elif selected_mode == "WALK":
                travel_duration = walking_duration_seconds
                route_distance = walking_distance_meters
            else:
                selected_mode = "DRIVE"
                travel_duration = driving_duration_seconds
                route_distance = driving_distance_meters

            if travel_duration is None:
                raise TravelProviderException(
                    f"Google Routes returned no estimate for mode {selected_mode}",
                    provider="google_routes",
                )

            if drive_est and hasattr(drive_est, "uncertainty_seconds") and drive_est.uncertainty_seconds:
                travel_uncertainty = drive_est.uncertainty_seconds
            else:
                travel_uncertainty = 300

            provider_name = (
                "google_routes"
                if is_google
                else "mock"
                if "mock" in self.provider.__class__.__name__.lower()
                else self.provider.__class__.__name__.lower().replace("provider", "")
            )
            travel_status = "OPTIMIZED"

            # Exact Recommended Departure Formula:
            # recommended_departure = predicted_turn_time - travel_duration - arrival_buffer
            recommended_departure = consultation_start - timedelta(seconds=travel_duration + buffer_seconds)
            departure_end = recommended_departure
            departure_start = departure_end - timedelta(seconds=buffer_seconds)

            # Planned Arrival Window at Hospital (buffer before consultation)
            half_window = 300  # 5 minutes
            arrival_end = consultation_start - timedelta(seconds=half_window)
            arrival_start = consultation_start - timedelta(seconds=buffer_seconds + half_window)

        except TravelProviderException as e:
            logger.warning(
                "Travel provider failure for entry %s: %s (status_code=%s).",
                entry.id,
                e.message,
                e.status_code,
            )
            travel_duration = None
            travel_uncertainty = None
            route_distance = None
            provider_name = "mock"
            travel_status = "DEGRADED"
            departure_start = None
            departure_end = None

        # Evaluate Meaningful Change (>= 10 minutes shift)
        consultation_changed = False
        travel_changed = False

        if prev_plan:
            p_cstart = prev_plan.consultation_start_at
            if p_cstart and p_cstart.tzinfo is None:
                p_cstart = p_cstart.replace(tzinfo=timezone.utc)
            c_start = consultation_start
            if c_start and c_start.tzinfo is None:
                c_start = c_start.replace(tzinfo=timezone.utc)
            c_delta = abs((c_start - p_cstart).total_seconds())
            if c_delta >= MEANINGFUL_CHANGE_THRESHOLD_SECONDS:
                consultation_changed = True

            if prev_plan.departure_start_at and departure_start:
                p_dstart = prev_plan.departure_start_at
                if p_dstart and p_dstart.tzinfo is None:
                    p_dstart = p_dstart.replace(tzinfo=timezone.utc)
                d_start = departure_start
                if d_start and d_start.tzinfo is None:
                    d_start = d_start.replace(tzinfo=timezone.utc)
                d_delta = abs((d_start - p_dstart).total_seconds())
                if d_delta >= MEANINGFUL_CHANGE_THRESHOLD_SECONDS:
                    travel_changed = True

        is_meaningful = consultation_changed or travel_changed

        # Build context-aware, patient-facing explanation
        if departure_start and departure_end:
            start_str = departure_start.strftime("%I:%M %p").lstrip("0")
            end_str = departure_end.strftime("%I:%M %p").lstrip("0")
        else:
            start_str = "—"
            end_str = "—"

        if travel_status == "CONFIGURATION_REQUIRED":
            explanation = "Travel estimates require Google Maps configuration. Please configure GOOGLE_ROUTES_API_KEY."
        elif travel_status in ("ERROR", "DEGRADED"):
            explanation = "Live route updates are temporarily unavailable. Your consultation estimate is still available."
        elif self.provider.__class__.__name__ == "MockTravelProvider":
            explanation = f"Development travel estimate ({start_str} – {end_str}). Configure GOOGLE_ROUTES_API_KEY for live traffic."
        elif consultation_changed and snapshot.explanation_text:
            explanation = (
                f"Your estimated consultation window shifted ({snapshot.explanation_text}). "
                f"Your recommended departure window has been updated to {start_str} – {end_str}."
            )
        elif travel_changed:
            explanation = (
                f"Transit conditions have shifted your travel time. "
                f"Your recommended departure window moved to {start_str} – {end_str}."
            )
        else:
            explanation = (
                f"Based on your estimated consultation window and live traffic conditions, "
                f"leaving between {start_str} and {end_str} should help you arrive before your consultation."
            )

        plan = ArrivalPlan(
            queue_entry_id=entry.id,
            prediction_snapshot_id=snapshot.id,
            travel_provider=provider_name,
            travel_status=travel_status,
            travel_duration_seconds=travel_duration,
            travel_uncertainty_seconds=travel_uncertainty,
            route_distance_meters=route_distance,
            driving_duration_seconds=driving_duration_seconds,
            driving_distance_meters=driving_distance_meters,
            bike_duration_seconds=bike_duration_seconds,
            bike_distance_meters=bike_distance_meters,
            walking_duration_seconds=walking_duration_seconds,
            walking_distance_meters=walking_distance_meters,
            selected_travel_mode=selected_mode,
            arrival_buffer_seconds=buffer_seconds,
            consultation_start_at=consultation_start,
            consultation_end_at=consultation_end,
            arrival_start_at=arrival_start if departure_start else None,
            arrival_end_at=arrival_end if departure_end else None,
            departure_start_at=departure_start,
            departure_end_at=departure_end,
            is_meaningful_change=is_meaningful,
            consultation_changed=consultation_changed,
            travel_changed=travel_changed,
            explanation=explanation,
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan
