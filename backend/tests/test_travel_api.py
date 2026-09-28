"""API and RBAC integration tests for Phase 5 Travel Origin and Arrival Optimization endpoints."""

import uuid
import pytest
from app.models.user import UserRole
from tests.conftest import make_test_user


def test_set_travel_origin_api_and_get_arrival_plan(test_client, db_session, seed_opd_data):
    """Verify patient can configure travel origin and receive arrival/departure recommendations."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "API Travel Pat 1", "apitravel1@test.com", UserRole.PATIENT)

    # 1. Join queue
    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    assert join_res.status_code == 201
    entry_id = join_res.json()["entry"]["id"]

    # 2. Configure travel origin
    origin_payload = {
        "latitude": 12.9352,
        "longitude": 77.6245,
        "travel_mode": "DRIVE",
    }
    origin_res = test_client.post(f"/api/v1/queue-entries/{entry_id}/travel-origin", json=origin_payload, headers=p_headers)
    assert origin_res.status_code == 200
    data = origin_res.json()

    assert data["queue_entry_id"] == entry_id
    if data["travel_status"] == "CONFIGURATION_REQUIRED":
        assert "Google Maps" in data["explanation"]
        assert data["arrival_buffer_minutes"] == 15
    else:
        assert data["travel_status"] in ("OPTIMIZED", "AVAILABLE")
        assert data["arrival_start_at"] is not None
        assert data["arrival_end_at"] is not None
        assert data["departure_start_at"] is not None
        assert data["departure_end_at"] is not None
        assert data["travel_duration_seconds"] > 0
        assert data["arrival_buffer_minutes"] == 15

    # 3. Get direct travel estimate
    travel_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/travel", headers=p_headers)
    assert travel_res.status_code == 200
    t_data = travel_res.json()
    if t_data["travel_status"] == "CONFIGURATION_REQUIRED":
        assert t_data["travel_duration_seconds"] is None
    else:
        assert t_data["travel_status"] in ("OPTIMIZED", "AVAILABLE")
        assert t_data["travel_duration_seconds"] > 0

    # 4. Get arrival plan
    plan_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/arrival-plan", headers=p_headers)
    assert plan_res.status_code == 200
    p_data = plan_res.json()
    assert p_data["queue_entry_id"] == entry_id

    # 5. Get arrival plan history
    hist_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/arrival-plan/history", headers=p_headers)
    assert hist_res.status_code == 200
    h_data = hist_res.json()
    assert h_data["total_plans"] >= 1

    # 6. Test mode switching endpoint (DRIVE -> TWO_WHEELER)
    mode_res = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/travel-mode",
        json={"travel_mode": "TWO_WHEELER"},
        headers=p_headers,
    )
    assert mode_res.status_code == 200
    m_data = mode_res.json()
    assert m_data["selected_travel_mode"] == "TWO_WHEELER"


def test_invalid_coordinates_validation_rejected(test_client, db_session, seed_opd_data):
    """Verify out-of-range latitude (> 90) or longitude (> 180) is rejected with HTTP 422."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Invalid Coord Pat", "invcoord@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    # Invalid latitude (> 90)
    res_lat = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/travel-origin",
        json={"latitude": 95.0, "longitude": 77.0, "travel_mode": "DRIVE"},
        headers=p_headers,
    )
    assert res_lat.status_code == 422

    # Invalid longitude (> 180)
    res_lng = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/travel-origin",
        json={"latitude": 12.0, "longitude": 185.0, "travel_mode": "DRIVE"},
        headers=p_headers,
    )
    assert res_lng.status_code == 422


def test_travel_origin_privacy_and_rbac(test_client, db_session, seed_opd_data):
    """Verify patient cannot view or set another patient's travel origin (403 Forbidden)."""
    queue = seed_opd_data["queue"]
    p1, p1_headers = make_test_user(db_session, "Travel Privacy 1", "tpriv1@test.com", UserRole.PATIENT)
    p2, p2_headers = make_test_user(db_session, "Travel Privacy 2", "tpriv2@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Travel Access", "stafftrav@test.com", UserRole.STAFF)

    # P1 joins queue and configures origin
    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p1_headers)
    e1_id = join_res.json()["entry"]["id"]

    test_client.post(
        f"/api/v1/queue-entries/{e1_id}/travel-origin",
        json={"latitude": 12.9352, "longitude": 77.6245, "travel_mode": "DRIVE"},
        headers=p1_headers,
    )

    # P2 attempts to read P1's travel estimate -> 403 Forbidden
    p2_travel = test_client.get(f"/api/v1/queue-entries/{e1_id}/travel", headers=p2_headers)
    assert p2_travel.status_code == 403

    # P2 attempts to read P1's arrival plan -> 403 Forbidden
    p2_plan = test_client.get(f"/api/v1/queue-entries/{e1_id}/arrival-plan", headers=p2_headers)
    assert p2_plan.status_code == 403

    # P2 attempts to mutate P1's origin -> 403 Forbidden
    p2_mut = test_client.post(
        f"/api/v1/queue-entries/{e1_id}/travel-origin",
        json={"latitude": 13.0, "longitude": 77.5, "travel_mode": "DRIVE"},
        headers=p2_headers,
    )
    assert p2_mut.status_code == 403

    # Staff can view P1's arrival plan -> 200 OK
    s_plan = test_client.get(f"/api/v1/queue-entries/{e1_id}/arrival-plan", headers=s_headers)
    assert s_plan.status_code == 200


def test_no_origin_returns_unavailable_state(test_client, db_session, seed_opd_data):
    """Verify that when no origin is set, arrival plan returns UNAVAILABLE status with helpful guidance."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "No Origin API Pat", "nooriginapi@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    plan_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/arrival-plan", headers=p_headers)
    assert plan_res.status_code == 200
    data = plan_res.json()

    assert data["travel_status"] == "UNAVAILABLE"
    assert data["arrival_start_at"] is None
    assert data["departure_start_at"] is None
    assert "Add your starting location" in data["explanation"]
