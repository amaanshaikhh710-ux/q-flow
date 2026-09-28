"""API and RBAC integration tests for Phase 4 prediction and reforecast endpoints."""

import uuid
import pytest
from app.models.user import UserRole
from app.models.queue_entry import QueueEntryStatus
from tests.conftest import make_test_user


def test_patient_can_view_own_prediction(test_client, db_session, seed_opd_data):
    """Verify patient can fetch their own prediction with honest uncertainty window."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "API Pred Pat 1", "apipred1@test.com", UserRole.PATIENT)

    # Join queue
    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    # Fetch prediction
    pred_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p_headers)
    assert pred_res.status_code == 200
    data = pred_res.json()
    assert data["queue_entry_id"] == entry_id
    assert "predicted_start_at" in data
    assert "predicted_end_at" in data
    assert data["uncertainty_minutes"] >= 3
    assert data["model_type"] in ("robust_median", "HistGradientBoostingRegressor")
    assert data["prediction_status"] in ("VALID", "FALLBACK")
    assert "explanation_text" in data


def test_patient_cannot_view_other_patients_prediction(test_client, db_session, seed_opd_data):
    """Verify patient privacy: Patient 2 is rejected with 403 Forbidden when viewing Patient 1's prediction."""
    queue = seed_opd_data["queue"]
    p1, p1_headers = make_test_user(db_session, "Pat 1 Privacy", "p1priv@test.com", UserRole.PATIENT)
    p2, p2_headers = make_test_user(db_session, "Pat 2 Privacy", "p2priv@test.com", UserRole.PATIENT)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p1_headers)
    entry_id = join_res.json()["entry"]["id"]

    # P2 attempts to read P1's prediction
    forbidden_res = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=p2_headers)
    assert forbidden_res.status_code == 403
    assert "Cannot view predictions for other patients" in forbidden_res.json()["detail"]


def test_staff_can_view_any_prediction_and_history(test_client, db_session, seed_opd_data):
    """Verify staff can access individual prediction and full history for any entry."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Hist", "phist@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Hist", "shist@test.com", UserRole.STAFF)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    entry_id = join_res.json()["entry"]["id"]

    # Staff views prediction
    s_pred = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction", headers=s_headers)
    assert s_pred.status_code == 200
    assert s_pred.json()["queue_entry_id"] == entry_id

    # Staff views prediction history
    s_hist = test_client.get(f"/api/v1/queue-entries/{entry_id}/prediction/history", headers=s_headers)
    assert s_hist.status_code == 200
    assert s_hist.json()["queue_entry_id"] == entry_id
    assert s_hist.json()["total_snapshots"] >= 1


def test_queue_prediction_board_rbac(test_client, db_session, seed_opd_data):
    """Verify staff can view queue prediction board; patient is forbidden (403) to prevent leaking other patients' ETAs."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Board", "pboard@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Board", "sboard@test.com", UserRole.STAFF)

    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)

    # Patient attempts to view queue board -> 403 Forbidden
    p_res = test_client.get(f"/api/v1/queues/{queue.id}/predictions", headers=p_headers)
    assert p_res.status_code == 403

    # Staff views queue board -> 200 OK
    s_res = test_client.get(f"/api/v1/queues/{queue.id}/predictions", headers=s_headers)
    assert s_res.status_code == 200
    data = s_res.json()
    assert data["queue_id"] == str(queue.id)
    assert data["active_count"] >= 1


def test_manual_reforecast_trigger_rbac(test_client, db_session, seed_opd_data):
    """Verify staff can manually trigger queue reforecast; patient is forbidden (403)."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Ref Trig", "preftrig@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Ref Trig", "sreftrig@test.com", UserRole.STAFF)

    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)

    # Patient attempts reforecast -> 403
    p_ref = test_client.post(f"/api/v1/queues/{queue.id}/reforecast", headers=p_headers)
    assert p_ref.status_code == 403

    # Staff triggers reforecast -> 200 OK
    s_ref = test_client.post(f"/api/v1/queues/{queue.id}/reforecast", headers=s_headers)
    assert s_ref.status_code == 200
    assert s_ref.json()["success"] is True
    assert s_ref.json()["reforecasted_count"] >= 1
