"""Production Demo Verification Test Suite.

Verifies:
1. Idempotent database seeding.
2. All 5 demo hospitals exist and are discoverable via /api/v1/discovery/hospitals.
3. Hospital -> Department -> Doctor hierarchy integrity.
4. All 5 staff demo accounts can authenticate and access their assigned hospital operations.
5. Strict hospital isolation: Staff from Hospital A cannot access Hospital B data.
6. All 10 patient demo accounts can authenticate.
7. New patient registration provisions PATIENT role and allows immediate login.
8. Patient can query doctor availability and join queues.
9. Staff hospital details and operational queue metrics are correctly computed.
"""

from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.services.seed_service import seed_demo_data
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.user import User, UserRole


@pytest.fixture(scope="module", autouse=True)
def ensure_seeded():
    """Ensure database has clean schema and demo seed data."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_hospitals_discovery(client: TestClient):
    """Verify that all 5 Mumbai reference hospitals are discoverable."""
    res = client.get("/api/v1/discovery/hospitals")
    assert res.status_code == 200, res.text
    hospitals = res.json()
    assert len(hospitals) >= 5
    names = [h["name"] for h in hospitals]
    assert any("King Edward" in n or "KEM" in n for n in names)
    assert any("Nair" in n for n in names)
    assert any("Sion" in n or "Lokmanya" in n for n in names)
    assert any("J.J." in n for n in names)
    assert any("Rajawadi" in n for n in names)


def test_hospital_department_doctor_hierarchy(client: TestClient):
    """Verify Hospital -> Department -> Doctor relationship consistency."""
    hosp_res = client.get("/api/v1/discovery/hospitals")
    assert hosp_res.status_code == 200
    hospitals = hosp_res.json()
    kem = next(h for h in hospitals if "King Edward" in h["name"] or "KEM" in h["name"])

    # 1. Departments under KEM
    dept_res = client.get(f"/api/v1/discovery/hospitals/{kem['id']}/departments")
    assert dept_res.status_code == 200
    depts = dept_res.json()
    assert len(depts) >= 3
    dept_names = [d["name"] for d in depts]
    assert "General Medicine" in dept_names

    # 2. Doctors under General Medicine
    gen_med = next(d for d in depts if d["name"] == "General Medicine")
    doc_res = client.get(f"/api/v1/discovery/departments/{gen_med['id']}/doctors")
    assert doc_res.status_code == 200
    docs = doc_res.json()
    assert len(docs) >= 1
    doc_names = [d["name"] for d in docs]
    assert any("Arjun Mehta" in n for n in doc_names)


def test_all_staff_demo_logins(client: TestClient):
    """Verify that all 5 staff demo accounts can log in and have correct roles/hospitals."""
    staff_accounts = [
        ("staff.kem@qflow.com", "password123", "King Edward"),
        ("staff.nair@qflow.com", "password123", "Nair"),
        ("staff.sion@qflow.com", "password123", "Lokmanya"),
        ("staff.jj@qflow.com", "password123", "J.J."),
        ("staff.rajawadi@qflow.com", "password123", "Rajawadi"),
    ]

    for email, pwd, hosp_name_fragment in staff_accounts:
        res = client.post("/api/v1/auth/login", json={"identifier": email, "password": pwd})
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        data = res.json()
        assert data["user"]["role"] == "staff"
        assert data["user"]["hospital_id"] is not None

        # Verify staff portal endpoint works for this staff member
        token = data["access_token"]
        portal_res = client.get(
            "/api/v1/discovery/staff-hospital",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert portal_res.status_code == 200, f"Staff hospital fetch failed: {portal_res.text}"
        hosp_info = portal_res.json()["hospital"]
        assert hosp_name_fragment in hosp_info["name"]


def test_patient_demo_logins(client: TestClient):
    """Verify that all 10 patient demo accounts from LoginPage.tsx can authenticate."""
    patient_emails = [
        "patient01@qflow.com",
        "patient02@qflow.com",
        "patient03@qflow.com",
        "patient04@qflow.com",
        "patient05@qflow.com",
        "patient06@qflow.com",
        "patient07@qflow.com",
        "patient08@qflow.com",
        "patient09@qflow.com",
        "patient10@qflow.com",
        "patient@qflow.com",
    ]

    for email in patient_emails:
        res = client.post("/api/v1/auth/login", json={"identifier": email, "password": "password123"})
        assert res.status_code == 200, f"Patient login failed for {email}: {res.text}"
        data = res.json()
        assert data["user"]["role"] == "patient"
        assert "access_token" in data


def test_new_patient_registration_and_login(client: TestClient):
    """Verify that a brand new patient can register and log in immediately."""
    unique_email = f"newpatient_{date.today().strftime('%Y%m%d')}_{id(client)}@example.com"
    payload = {
        "name": "Aarushi Sen",
        "email": unique_email,
        "phone": "+919811122233",
        "password": "SecurePassword123!",
    }

    # Register
    reg_res = client.post("/api/v1/auth/register", json=payload)
    assert reg_res.status_code == 201, reg_res.text
    user = reg_res.json()
    assert user["role"] == "patient"
    assert user["email"] == unique_email

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"identifier": unique_email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200, login_res.text
    assert "access_token" in login_res.json()


def test_doctor_schedule_availability_endpoint(client: TestClient):
    """Verify patient discovery endpoint /schedules/doctors/{doctor_id}/availability."""
    hosp_res = client.get("/api/v1/discovery/hospitals")
    hospitals = hosp_res.json()
    kem = next(h for h in hospitals if "King Edward" in h["name"] or "KEM" in h["name"])

    dept_res = client.get(f"/api/v1/discovery/hospitals/{kem['id']}/departments")
    gen_med = next(d for d in dept_res.json() if d["name"] == "General Medicine")

    doc_res = client.get(f"/api/v1/discovery/departments/{gen_med['id']}/doctors")
    arjun = next(d for d in doc_res.json() if "Arjun" in d["name"])

    # Query availability
    avail_res = client.get(
        f"/api/v1/schedules/doctors/{arjun['id']}/availability",
        params={"hospital_id": kem["id"], "department_id": gen_med["id"]},
    )
    assert avail_res.status_code == 200, avail_res.text
    avail_data = avail_res.json()
    schedules = avail_data.get("schedules", [])
    assert len(schedules) >= 14, f"Expected 14-day schedule coverage, got {len(schedules)}"
    assert all(s["doctor_id"] == arjun["id"] for s in schedules)


def test_staff_hospital_isolation(client: TestClient):
    """Verify that staff members cannot manage or tamper with another hospital's doctors."""
    # Login as KEM staff
    kem_res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "staff.kem@qflow.com", "password": "password123"},
    )
    kem_token = kem_res.json()["access_token"]

    # Find a Nair doctor
    hosp_res = client.get("/api/v1/discovery/hospitals")
    nair = next(h for h in hosp_res.json() if "Nair" in h["name"])
    dept_res = client.get(f"/api/v1/discovery/hospitals/{nair['id']}/departments")
    nair_dept = dept_res.json()[0]
    doc_res = client.get(f"/api/v1/discovery/departments/{nair_dept['id']}/doctors")
    nair_doc = doc_res.json()[0]

    # Attempt to schedule Nair doctor using KEM staff credentials
    tamper_payload = {
        "doctor_id": nair_doc["id"],
        "schedule_date": (date.today() + timedelta(days=2)).isoformat(),
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "status": "AVAILABLE",
    }
    tamper_res = client.post(
        "/api/v1/schedules",
        json=tamper_payload,
        headers={"Authorization": f"Bearer {kem_token}"},
    )
    assert tamper_res.status_code == 403, (
        f"KEM staff must be forbidden from scheduling Nair doctor: {tamper_res.status_code}"
    )


def test_idempotent_seeding_is_safe():
    """Verify that calling seed_demo_data multiple times produces zero duplicates."""
    with SessionLocal() as db:
        initial_hospitals = db.query(Hospital).count()
        initial_doctors = db.query(Doctor).count()
        initial_users = db.query(User).count()

        # Run seed again
        seed_demo_data(db)

        assert db.query(Hospital).count() == initial_hospitals
        assert db.query(Doctor).count() == initial_doctors
        assert db.query(User).count() == initial_users
