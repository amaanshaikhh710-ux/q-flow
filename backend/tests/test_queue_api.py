"""Comprehensive API and RBAC test suite for Q-FLOW Core Queue Engine endpoints."""

import uuid
import pytest
from app.models.user import UserRole
from app.models.queue import QueueStatus
from app.models.queue_entry import QueueEntryStatus, PriorityClass
from app.services.queue_engine import QueueEngineService
from tests.conftest import make_test_user


def test_patient_join_queue_api(test_client, db_session, seed_opd_data):
    """Verify patient can join active queue via HTTP and receives authoritative token."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "API Pat 1", "apipat1@test.com", UserRole.PATIENT)

    # Missing auth -> 401
    unauth_res = test_client.post(f"/api/v1/queues/{queue.id}/join")
    assert unauth_res.status_code == 401

    # Valid join
    res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    assert res.status_code == 201
    data = res.json()
    assert "entry" in data
    entry_data = data["entry"]
    assert entry_data["token_number"] == 1
    assert entry_data["token_display"] == "Q001"
    assert entry_data["position"] == 1
    assert entry_data["status"] == "WAITING"
    assert entry_data["patient_user_id"] == str(patient.id)


def test_duplicate_join_api_rejection(test_client, db_session, seed_opd_data):
    """Verify patient cannot join the same queue twice while active."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "API Pat Dup", "apipatdup@test.com", UserRole.PATIENT)

    res1 = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    assert res1.status_code == 201

    res2 = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)
    assert res2.status_code == 409
    assert "already has an active ticket" in res2.json()["detail"]


def test_get_queue_and_snapshot_api(test_client, db_session, seed_opd_data):
    """Verify fetching queue details and snapshot via API."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "API Snapshot Pat", "snap@test.com", UserRole.PATIENT)

    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)

    # Queue details
    q_res = test_client.get(f"/api/v1/queues/{queue.id}", headers=p_headers)
    assert q_res.status_code == 200
    assert q_res.json()["name"] == queue.name

    # Snapshot
    snap_res = test_client.get(f"/api/v1/queues/{queue.id}/snapshot", headers=p_headers)
    assert snap_res.status_code == 200
    snap = snap_res.json()
    assert snap["queue_id"] == str(queue.id)
    assert snap["total_waiting"] == 1
    assert snap["next_patient"]["token_display"] == "Q001"


def test_call_next_rbac(test_client, db_session, seed_opd_data):
    """Verify only STAFF or ADMIN can call next patient; PATIENT is blocked with 403."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Call", "patcall@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Call", "staffcall@test.com", UserRole.STAFF)
    admin, a_headers = make_test_user(db_session, "Admin Call", "admincall@test.com", UserRole.ADMIN)

    # Patient joins
    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers)

    # Patient attempts to call next -> 403 Forbidden
    res_pat = test_client.post(f"/api/v1/queues/{queue.id}/call-next", headers=p_headers)
    assert res_pat.status_code == 403

    # Staff calls next -> 200 OK
    res_staff = test_client.post(f"/api/v1/queues/{queue.id}/call-next", headers=s_headers)
    assert res_staff.status_code == 200
    assert res_staff.json()["status"] == "CALLED"
    assert res_staff.json()["position"] == 0

    # Another patient joins
    p2, p2_headers = make_test_user(db_session, "Pat 2 Call", "pat2call@test.com", UserRole.PATIENT)
    test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p2_headers)

    # Admin calls next -> 200 OK
    res_admin = test_client.post(f"/api/v1/queues/{queue.id}/call-next", headers=a_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["status"] == "CALLED"


def test_consultation_lifecycle_api(test_client, db_session, seed_opd_data):
    """Verify staff start and complete consultation lifecycle via HTTP."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Consult", "pconsult@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Consult", "sconsult@test.com", UserRole.STAFF)

    # Join and call
    join_data = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers).json()
    entry_id = join_data["entry"]["id"]
    test_client.post(f"/api/v1/queues/{queue.id}/call-next", headers=s_headers)

    # Patient attempts start consultation -> 403
    p_start = test_client.post(f"/api/v1/queue-entries/{entry_id}/start-consultation", headers=p_headers)
    assert p_start.status_code == 403

    # Staff starts consultation -> 200
    s_start = test_client.post(f"/api/v1/queue-entries/{entry_id}/start-consultation", headers=s_headers)
    assert s_start.status_code == 200
    assert s_start.json()["status"] == "IN_CONSULTATION"

    # Duplicate start -> 409
    dup_start = test_client.post(f"/api/v1/queue-entries/{entry_id}/start-consultation", headers=s_headers)
    assert dup_start.status_code == 409

    # Staff completes consultation -> 200
    s_comp = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/complete-consultation",
        headers=s_headers,
        json={"interruption_notes": "Prescribed antibiotic course"},
    )
    assert s_comp.status_code == 200
    assert s_comp.json()["status"] == "COMPLETED"

    # Duplicate complete -> 409
    dup_comp = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/complete-consultation",
        headers=s_headers,
        json={},
    )
    assert dup_comp.status_code == 409


def test_no_show_api(test_client, db_session, seed_opd_data):
    """Verify staff can mark no-show; patient forbidden."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat NS API", "pnsapi@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff NS API", "snsapi@test.com", UserRole.STAFF)

    join_data = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers).json()
    entry_id = join_data["entry"]["id"]

    # Patient cannot mark no-show
    res_pat = test_client.post(f"/api/v1/queue-entries/{entry_id}/no-show", headers=p_headers, json={})
    assert res_pat.status_code == 403

    # Staff marks no-show
    res_staff = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/no-show",
        headers=s_headers,
        json={"reason": "Patient left waiting room"},
    )
    assert res_staff.status_code == 200
    assert res_staff.json()["status"] == "NO_SHOW"


def test_temporary_leave_return_and_requeue_api(test_client, db_session, seed_opd_data):
    """Verify leave, return, and staff requeue workflow with ownership & RBAC enforcement."""
    queue = seed_opd_data["queue"]
    p1, p1_headers = make_test_user(db_session, "Pat Leave 1", "pleave1@test.com", UserRole.PATIENT)
    p2, p2_headers = make_test_user(db_session, "Pat Leave 2", "pleave2@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Requeue API", "srqapi@test.com", UserRole.STAFF)

    join_data = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p1_headers).json()
    entry_id = join_data["entry"]["id"]

    # Patient attempts to record temporary leave -> 403 Forbidden
    res_pat_leave = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/leave",
        headers=p1_headers,
        json={"reason": "Getting blood sample collected"},
    )
    assert res_pat_leave.status_code == 403

    # Staff records temporary leave -> 200 OK
    res_staff_leave = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/leave",
        headers=s_headers,
        json={"reason": "Getting blood sample collected"},
    )
    assert res_staff_leave.status_code == 200
    assert res_staff_leave.json()["status"] == "TEMPORARILY_LEFT"

    # Patient attempts to record return -> 403 Forbidden
    res_pat_ret = test_client.post(f"/api/v1/queue-entries/{entry_id}/return", headers=p1_headers)
    assert res_pat_ret.status_code == 403

    # Staff records patient return -> 200 OK
    res_staff_ret = test_client.post(f"/api/v1/queue-entries/{entry_id}/return", headers=s_headers)
    assert res_staff_ret.status_code == 200
    assert res_staff_ret.json()["status"] == "RETURNED"

    # Patient cannot requeue themselves -> 403
    res_self_rq = test_client.post(f"/api/v1/queue-entries/{entry_id}/requeue", headers=p1_headers, json={})
    assert res_self_rq.status_code == 403

    # Staff requeues patient back into active WAITING -> 200 OK
    res_rq = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/requeue",
        headers=s_headers,
        json={"priority_class": "normal", "reason": "Patient returned to waiting area"},
    )
    assert res_rq.status_code == 200
    assert res_rq.json()["status"] == "WAITING"


def test_priority_and_emergency_api(test_client, db_session, seed_opd_data):
    """Verify priority changes and emergency insertions via staff API."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Prio API", "pprioapi@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Prio API", "sprioapi@test.com", UserRole.STAFF)

    join_data = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p_headers).json()
    entry_id = join_data["entry"]["id"]

    # Patient attempts to elevate own priority -> 403
    p_promo = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/priority",
        headers=p_headers,
        json={"priority_class": "priority"},
    )
    assert p_promo.status_code == 403

    # Staff changes priority to PRIORITY
    s_prio = test_client.post(
        f"/api/v1/queue-entries/{entry_id}/priority",
        headers=s_headers,
        json={"priority_class": "priority", "reason": "Severe pain"},
    )
    assert s_prio.status_code == 200
    assert s_prio.json()["priority_class"] == "priority"

    # Staff inserts emergency patient
    emerg_pat, _ = make_test_user(db_session, "Emergency Patient API", "emgapi@test.com", UserRole.PATIENT)
    s_emerg = test_client.post(
        f"/api/v1/queues/{queue.id}/emergency",
        headers=s_headers,
        json={"patient_user_id": str(emerg_pat.id), "reason": "Critical trauma triage"},
    )
    assert s_emerg.status_code == 201
    assert s_emerg.json()["priority_class"] == "emergency"
    assert s_emerg.json()["position"] == 1


def test_doctor_delays_breaks_and_pause_resume_api(test_client, db_session, seed_opd_data):
    """Verify operational disruptions and queue pause/resume controls."""
    queue = seed_opd_data["queue"]
    patient, p_headers = make_test_user(db_session, "Pat Disrupt", "pdis@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Disrupt", "sdis@test.com", UserRole.STAFF)

    # Delay
    assert test_client.post(
        f"/api/v1/queues/{queue.id}/doctor-delay",
        headers=p_headers,
        json={"delay_minutes": 20},
    ).status_code == 403

    res_delay = test_client.post(
        f"/api/v1/queues/{queue.id}/doctor-delay",
        headers=s_headers,
        json={"delay_minutes": 20, "reason": "Emergency surgery delay"},
    )
    assert res_delay.status_code == 200
    assert res_delay.json()["delay_minutes"] == 20

    # Break start & end
    res_bstart = test_client.post(
        f"/api/v1/queues/{queue.id}/doctor-break/start",
        headers=s_headers,
        json={"duration_minutes": 15, "reason": "Coffee break"},
    )
    assert res_bstart.status_code == 200

    res_bend = test_client.post(
        f"/api/v1/queues/{queue.id}/doctor-break/end",
        headers=s_headers,
    )
    assert res_bend.status_code == 200

    # Pause & Resume
    res_pause = test_client.post(f"/api/v1/queues/{queue.id}/pause", headers=s_headers)
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "paused"

    res_resume = test_client.post(f"/api/v1/queues/{queue.id}/resume", headers=s_headers)
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "active"


def test_entry_ownership_privacy(test_client, db_session, seed_opd_data):
    """Verify patients can only read their own queue tickets; staff can read all."""
    queue = seed_opd_data["queue"]
    p1, p1_headers = make_test_user(db_session, "Pat Own 1", "pown1@test.com", UserRole.PATIENT)
    p2, p2_headers = make_test_user(db_session, "Pat Own 2", "pown2@test.com", UserRole.PATIENT)
    staff, s_headers = make_test_user(db_session, "Staff Own", "sown@test.com", UserRole.STAFF)

    join_res = test_client.post(f"/api/v1/queues/{queue.id}/join", headers=p1_headers)
    entry_id = join_res.json()["entry"]["id"]

    # P1 reading own ticket -> 200
    assert test_client.get(f"/api/v1/queue-entries/{entry_id}", headers=p1_headers).status_code == 200

    # P2 reading P1's ticket -> 403 Forbidden
    assert test_client.get(f"/api/v1/queue-entries/{entry_id}", headers=p2_headers).status_code == 403

    # Staff reading P1's ticket -> 200
    assert test_client.get(f"/api/v1/queue-entries/{entry_id}", headers=s_headers).status_code == 200
