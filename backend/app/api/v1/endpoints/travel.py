"""Travel origin and arrival optimization API endpoints."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.models.queue_entry import QueueEntry
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.schemas.travel import (
    TravelOriginRequest,
    TravelModeUpdateRequest,
    TravelEstimateResponse,
    ArrivalPlanResponse,
    ArrivalPlanHistoryResponse,
    ResolveAddressRequest,
    ResolveAddressResponse,
    ResolvedLocationItem,
)
from app.services.arrival_optimizer import ArrivalOptimizationService
from app.services.reforecast_service import PredictionService

router = APIRouter()
arrival_service = ArrivalOptimizationService()
prediction_service = PredictionService()


def _serialize_arrival_plan(plan: ArrivalPlan, entry: Optional[QueueEntry] = None) -> ArrivalPlanResponse:
    """Convert database ArrivalPlan into client response schema."""
    dur_mins = int(round(plan.travel_duration_seconds / 60)) if plan.travel_duration_seconds is not None else None
    unc_mins = int(round(plan.travel_uncertainty_seconds / 60)) if plan.travel_uncertainty_seconds is not None else None

    driving_secs = plan.driving_duration_seconds
    driving_mins = int(round(driving_secs / 60)) if driving_secs is not None else None
    driving_dist = plan.driving_distance_meters

    bike_secs = plan.bike_duration_seconds
    bike_mins = int(round(bike_secs / 60)) if bike_secs is not None else None
    bike_dist = plan.bike_distance_meters

    walking_secs = plan.walking_duration_seconds
    walking_mins = int(round(walking_secs / 60)) if walking_secs is not None else None

    # Origin address from entry or plan relationship
    origin_addr = None
    if entry and entry.origin_address:
        origin_addr = entry.origin_address
    elif plan.queue_entry and plan.queue_entry.origin_address:
        origin_addr = plan.queue_entry.origin_address

    sel_mode = getattr(plan, "selected_travel_mode", None) or (entry.travel_mode if entry else "DRIVE")

    return ArrivalPlanResponse(
        id=plan.id,
        queue_entry_id=plan.queue_entry_id,
        prediction_snapshot_id=plan.prediction_snapshot_id,
        travel_provider=plan.travel_provider,
        travel_status=plan.travel_status,
        consultation_start_at=plan.consultation_start_at,
        consultation_end_at=plan.consultation_end_at,
        arrival_start_at=plan.arrival_start_at,
        arrival_end_at=plan.arrival_end_at,
        departure_start_at=plan.departure_start_at,
        departure_end_at=plan.departure_end_at,
        travel_duration_seconds=plan.travel_duration_seconds,
        travel_duration_minutes=dur_mins,
        travel_uncertainty_seconds=plan.travel_uncertainty_seconds,
        travel_uncertainty_minutes=unc_mins,
        route_distance_meters=plan.route_distance_meters,
        driving_duration_seconds=driving_secs,
        driving_duration_minutes=driving_mins,
        driving_distance_meters=driving_dist,
        bike_duration_seconds=bike_secs,
        bike_duration_minutes=bike_mins,
        bike_distance_meters=bike_dist,
        walking_duration_seconds=walking_secs,
        walking_duration_minutes=walking_mins,
        walking_distance_meters=plan.walking_distance_meters,
        selected_travel_mode=sel_mode,
        origin_address=origin_addr,
        arrival_buffer_minutes=int(round(plan.arrival_buffer_seconds / 60)),
        is_meaningful_change=plan.is_meaningful_change,
        consultation_changed=plan.consultation_changed,
        travel_changed=plan.travel_changed,
        explanation=plan.explanation,
        created_at=plan.created_at,
    )


def _check_entry_access(entry: QueueEntry, current_user: User) -> None:
    """Ensure patient only views/mutates their own ticket; Staff/Admin can access all."""
    if current_user.role == UserRole.PATIENT and entry.patient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot view or update travel details for other patients' tickets",
        )


@router.post("/queue-entries/{entry_id}/travel-origin", response_model=ArrivalPlanResponse)
def set_travel_origin(
    entry_id: uuid.UUID,
    payload: TravelOriginRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArrivalPlanResponse:
    """Patient or staff sets the starting travel coordinates for an active queue entry."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    _check_entry_access(entry, current_user)

    # Update transient travel origin
    entry.origin_latitude = Decimal(str(payload.latitude))
    entry.origin_longitude = Decimal(str(payload.longitude))
    if payload.origin_address:
        entry.origin_address = payload.origin_address
    entry.travel_mode = payload.travel_mode
    entry.travel_origin_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)

    # Fetch latest prediction snapshot (or generate initial if none exists)
    latest_snap = (
        db.query(PredictionSnapshot)
        .filter(PredictionSnapshot.queue_entry_id == entry.id)
        .order_by(desc(PredictionSnapshot.created_at))
        .first()
    )
    if not latest_snap:
        latest_snap = prediction_service.generate_initial_prediction(db, entry.id)

    if not latest_snap:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction unavailable; cannot calculate arrival plan",
        )

    # Compute arrival plan
    plan = arrival_service.calculate_arrival_plan(db, entry, latest_snap, selected_travel_mode=payload.travel_mode)
    return _serialize_arrival_plan(plan, entry)


@router.post("/queue-entries/{entry_id}/travel-mode", response_model=ArrivalPlanResponse)
def set_travel_mode(
    entry_id: uuid.UUID,
    payload: TravelModeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArrivalPlanResponse:
    """Switch active travel mode (DRIVE, TWO_WHEELER, WALK) and recalculate departure immediately."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    _check_entry_access(entry, current_user)

    entry.travel_mode = payload.travel_mode
    db.commit()
    db.refresh(entry)

    latest_snap = (
        db.query(PredictionSnapshot)
        .filter(PredictionSnapshot.queue_entry_id == entry.id)
        .order_by(desc(PredictionSnapshot.created_at))
        .first()
    )
    if not latest_snap:
        latest_snap = prediction_service.generate_initial_prediction(db, entry.id)

    if not latest_snap:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction unavailable; cannot calculate arrival plan",
        )

    plan = arrival_service.calculate_arrival_plan(db, entry, latest_snap, selected_travel_mode=payload.travel_mode)
    return _serialize_arrival_plan(plan, entry)


@router.get("/queue-entries/{entry_id}/travel", response_model=TravelEstimateResponse)
def get_travel_estimate(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TravelEstimateResponse:
    """Get the latest direct transit duration and uncertainty estimate across all modes."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    _check_entry_access(entry, current_user)

    now = datetime.now(timezone.utc)

    if entry.origin_latitude is None or entry.origin_longitude is None:
        return TravelEstimateResponse(
            travel_duration_seconds=None,
            travel_duration_minutes=None,
            travel_uncertainty_seconds=None,
            travel_uncertainty_minutes=None,
            route_distance_meters=None,
            provider="none",
            travel_status="UNAVAILABLE",
            is_traffic_aware=False,
            calculated_at=now,
        )

    api_key = settings.canonical_google_routes_api_key
    if not api_key or not api_key.strip() or api_key.startswith("your-google-"):
        return TravelEstimateResponse(
            travel_duration_seconds=None,
            travel_duration_minutes=None,
            travel_uncertainty_seconds=None,
            travel_uncertainty_minutes=None,
            route_distance_meters=None,
            provider="google_routes",
            travel_status="CONFIGURATION_REQUIRED",
            is_traffic_aware=False,
            calculated_at=now,
        )

    h_lat, h_lng = arrival_service._get_hospital_coordinates(db, entry)
    try:
        modes = arrival_service.provider.estimate_all_modes(
            origin_lat=float(entry.origin_latitude),
            origin_lng=float(entry.origin_longitude),
            dest_lat=h_lat,
            dest_lng=h_lng,
        )
    except Exception:
        modes = {}

    drive_est = modes.get("DRIVE")
    bike_est = modes.get("TWO_WHEELER")
    walk_est = modes.get("WALK")

    # Active mode fallback to DRIVE
    active_mode = entry.travel_mode or "DRIVE"
    active_est = modes.get(active_mode) or drive_est or bike_est or walk_est

    if not active_est:
        return TravelEstimateResponse(
            travel_duration_seconds=None,
            travel_duration_minutes=None,
            travel_uncertainty_seconds=None,
            travel_uncertainty_minutes=None,
            route_distance_meters=None,
            provider="none",
            travel_status="UNAVAILABLE",
            is_traffic_aware=False,
            calculated_at=now,
        )

    dur_mins = int(round(active_est.duration_seconds / 60))
    unc_mins = int(round(active_est.uncertainty_seconds / 60))

    return TravelEstimateResponse(
        travel_duration_seconds=active_est.duration_seconds,
        travel_duration_minutes=dur_mins,
        travel_uncertainty_seconds=active_est.uncertainty_seconds,
        travel_uncertainty_minutes=unc_mins,
        route_distance_meters=active_est.distance_meters,
        driving_duration_seconds=drive_est.duration_seconds if drive_est else None,
        driving_duration_minutes=int(round(drive_est.duration_seconds / 60)) if drive_est else None,
        driving_distance_meters=drive_est.distance_meters if drive_est else None,
        bike_duration_seconds=bike_est.duration_seconds if bike_est else None,
        bike_duration_minutes=int(round(bike_est.duration_seconds / 60)) if bike_est else None,
        bike_distance_meters=bike_est.distance_meters if bike_est else None,
        walking_duration_seconds=walk_est.duration_seconds if walk_est else None,
        walking_duration_minutes=int(round(walk_est.duration_seconds / 60)) if walk_est else None,
        walking_distance_meters=walk_est.distance_meters if walk_est else None,
        provider=active_est.provider,
        travel_status=active_est.travel_status,
        is_traffic_aware=active_est.is_traffic_aware,
        calculated_at=active_est.calculated_at,
    )


@router.get("/queue-entries/{entry_id}/arrival-plan", response_model=ArrivalPlanResponse)
def get_arrival_plan(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArrivalPlanResponse:
    """Get latest departure recommendation and arrival window for patient ticket."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    _check_entry_access(entry, current_user)

    # Fetch latest arrival plan
    latest_plan = (
        db.query(ArrivalPlan)
        .filter(ArrivalPlan.queue_entry_id == entry.id)
        .order_by(desc(ArrivalPlan.created_at))
        .first()
    )

    if not latest_plan:
        # Check if prediction exists
        latest_snap = (
            db.query(PredictionSnapshot)
            .filter(PredictionSnapshot.queue_entry_id == entry.id)
            .order_by(desc(PredictionSnapshot.created_at))
            .first()
        )
        if not latest_snap:
            latest_snap = prediction_service.generate_initial_prediction(db, entry.id)

        if latest_snap:
            latest_plan = arrival_service.calculate_arrival_plan(db, entry, latest_snap)

    if not latest_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No arrival plan currently exists for this ticket",
        )

    return _serialize_arrival_plan(latest_plan, entry)


@router.get("/queue-entries/{entry_id}/arrival-plan/history", response_model=ArrivalPlanHistoryResponse)
def get_arrival_plan_history(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArrivalPlanHistoryResponse:
    """Get complete chronological timeline of arrival plans and departure updates."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry with ID {entry_id} does not exist",
        )

    _check_entry_access(entry, current_user)

    plans = (
        db.query(ArrivalPlan)
        .filter(ArrivalPlan.queue_entry_id == entry.id)
        .order_by(ArrivalPlan.created_at.asc())
        .all()
    )

    return ArrivalPlanHistoryResponse(
        queue_entry_id=entry.id,
        total_plans=len(plans),
        history=[_serialize_arrival_plan(p, entry) for p in plans],
    )


MUMBAI_LANDMARKS = [
    {"name": "Mumbra", "formatted_address": "Mumbra, Thane District, Maharashtra", "latitude": 19.1912, "longitude": 73.0234},
    {"name": "Mumbra Railway Station", "formatted_address": "Mumbra Railway Station, Thane District, Maharashtra", "latitude": 19.1895, "longitude": 73.0227},
    {"name": "Thane West", "formatted_address": "Thane West, Thane, Maharashtra", "latitude": 19.1982, "longitude": 72.9781},
    {"name": "Thane Station", "formatted_address": "Thane Railway Station, Thane West, Maharashtra", "latitude": 19.1860, "longitude": 72.9759},
    {"name": "Dadar", "formatted_address": "Dadar, Mumbai, Maharashtra", "latitude": 19.0178, "longitude": 72.8478},
    {"name": "Dadar West", "formatted_address": "Dadar West, Mumbai, Maharashtra", "latitude": 19.0208, "longitude": 72.8397},
    {"name": "Vashi", "formatted_address": "Vashi, Navi Mumbai, Maharashtra", "latitude": 19.0771, "longitude": 72.9986},
    {"name": "Sector 17 Vashi", "formatted_address": "Sector 17, Vashi, Navi Mumbai, Maharashtra", "latitude": 19.0735, "longitude": 72.9997},
    {"name": "Kurla", "formatted_address": "Kurla, Mumbai, Maharashtra", "latitude": 19.0726, "longitude": 72.8845},
    {"name": "Andheri", "formatted_address": "Andheri, Mumbai, Maharashtra", "latitude": 19.1136, "longitude": 72.8697},
    {"name": "Andheri West", "formatted_address": "Andheri West, Mumbai, Maharashtra", "latitude": 19.1197, "longitude": 72.8464},
    {"name": "Bandra", "formatted_address": "Bandra West, Mumbai, Maharashtra", "latitude": 19.0596, "longitude": 72.8295},
    {"name": "Borivali", "formatted_address": "Borivali West, Mumbai, Maharashtra", "latitude": 19.2307, "longitude": 72.8567},
    {"name": "Chembur", "formatted_address": "Chembur, Mumbai, Maharashtra", "latitude": 19.0522, "longitude": 72.8995},
    {"name": "Ghatkopar", "formatted_address": "Ghatkopar, Mumbai, Maharashtra", "latitude": 19.0860, "longitude": 72.9090},
    {"name": "Kalyan", "formatted_address": "Kalyan, Maharashtra", "latitude": 19.2403, "longitude": 73.1305},
    {"name": "Dombivli", "formatted_address": "Dombivli, Maharashtra", "latitude": 19.2183, "longitude": 73.0867},
    {"name": "Panvel", "formatted_address": "Panvel, Navi Mumbai, Maharashtra", "latitude": 18.9894, "longitude": 73.1175},
    {"name": "Parel", "formatted_address": "Parel, Mumbai, Maharashtra", "latitude": 19.0033, "longitude": 72.8423},
    {"name": "Worli", "formatted_address": "Worli, Mumbai, Maharashtra", "latitude": 19.0166, "longitude": 72.8168},
    {"name": "Byculla", "formatted_address": "Byculla, Mumbai, Maharashtra", "latitude": 18.9750, "longitude": 72.8333},
    {"name": "Mumbai Central", "formatted_address": "Mumbai Central, Mumbai, Maharashtra", "latitude": 18.9690, "longitude": 72.8205},
]


@router.post("/resolve-address", response_model=ResolveAddressResponse)
@router.post("/travel/resolve-address", response_model=ResolveAddressResponse)
def resolve_address(
    payload: ResolveAddressRequest,
) -> ResolveAddressResponse:
    """Resolve a textual area, landmark, or address query to coordinates using Google Geocoding or local MMR directory."""
    import httpx
    q = payload.query.strip()
    api_key = settings.canonical_google_routes_api_key

    # If Google Maps key configured, try Google Geocoding API first
    if api_key and not api_key.startswith("your-google-"):
        try:
            geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={q}&key={api_key}"
            with httpx.Client(timeout=5.0) as client:
                res = client.get(geo_url)
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("results", [])[:5]:
                        loc = item.get("geometry", {}).get("location", {})
                        results.append(
                            ResolvedLocationItem(
                                name=item.get("formatted_address", q).split(",")[0],
                                formatted_address=item.get("formatted_address", q),
                                latitude=loc.get("lat", 0.0),
                                longitude=loc.get("lng", 0.0),
                            )
                        )
                    if results:
                        return ResolveAddressResponse(
                            query=q,
                            results=results,
                            resolved_by="google_geocoding",
                        )
        except Exception:
            pass

    # Fallback to local landmark directory
    q_lower = q.lower()
    matches = []
    for lm in MUMBAI_LANDMARKS:
        if q_lower in lm["name"].lower() or q_lower in lm["formatted_address"].lower():
            matches.append(ResolvedLocationItem(**lm))

    if not matches:
        # Check words
        words = [w for w in q_lower.split() if len(w) > 2]
        for lm in MUMBAI_LANDMARKS:
            if any(w in lm["name"].lower() for w in words):
                if not any(m.name == lm["name"] for m in matches):
                    matches.append(ResolvedLocationItem(**lm))

    if not matches:
        # Default match to Mumbra if user queried mumbra-like or Thane
        matches.append(
            ResolvedLocationItem(
                name=q,
                formatted_address=f"{q}, Mumbai Metropolitan Region, Maharashtra",
                latitude=19.1912,
                longitude=73.0234,
            )
        )

    return ResolveAddressResponse(
        query=q,
        results=matches[:5],
        resolved_by="local_directory",
    )

