"""Pytest test configuration and fixtures."""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Create a file-backed SQLite test engine to avoid in-memory cross-connection quirks
TEST_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_sqlite.db"))
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Import the database module first so we can patch its engine/session BEFORE the application
import app.core.database as db_module
# Monkey-patch the database module so any import using app.core.database references the test engine/session
db_module.engine = test_engine
db_module.SessionLocal = TestSessionLocal

# Now import the FastAPI app (so startup checks will use the patched test engine)
from app.main import app
from app.core.database import Base, get_db
from app.models import *  # Ensure all models are loaded

# Create all tables in the test engine
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Provides an isolated transactional database session rolled back after each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    session.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_client(db_session):
    """Provides a FastAPI TestClient bound to the transactional db_session."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def seed_opd_data(db_session):
    """Seed a hospital, department, doctor, active OPD session, active Queue, and DoctorSchedule."""
    from datetime import datetime, timezone, date, time
    from app.models.hospital import Hospital
    from app.models.department import Department
    from app.models.doctor import Doctor, DoctorStatus
    from app.models.opd_session import OPDSession, SessionStatus
    from app.models.queue import Queue, QueueStatus
    from app.models.doctor_schedule import DoctorSchedule

    hospital = Hospital(name="Test Central Hospital", address="100 Health Way")
    db_session.add(hospital)
    db_session.flush()

    dept = Department(hospital_id=hospital.id, name="General Medicine")
    db_session.add(dept)
    db_session.flush()

    doctor = Doctor(department_id=dept.id, name="Dr. Test Physician", status=DoctorStatus.AVAILABLE)
    db_session.add(doctor)
    db_session.flush()

    opd_session = OPDSession(
        department_id=dept.id,
        doctor_id=doctor.id,
        starts_at=datetime.now(timezone.utc),
        status=SessionStatus.ACTIVE,
    )
    db_session.add(opd_session)
    db_session.flush()

    queue = Queue(
        opd_session_id=opd_session.id,
        name="General OPD Room 101",
        status=QueueStatus.ACTIVE,
    )
    db_session.add(queue)
    db_session.flush()

    sched = DoctorSchedule(
        hospital_id=hospital.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        schedule_date=date.today(),
        start_time=time(8, 0),
        end_time=time(18, 0),
        status="AVAILABLE",
        opd_session_id=opd_session.id,
    )
    db_session.add(sched)
    db_session.flush()

    return {
        "hospital": hospital,
        "department": dept,
        "doctor": doctor,
        "opd_session": opd_session,
        "queue": queue,
        "schedule": sched,
    }


def make_test_user(db_session, name: str, email: str, role: UserRole, hospital_id=None) -> tuple[User, dict]:
    """Helper to create a test user and return (User, headers_dict)."""
    from app.core.security import hash_password, create_access_token
    if role == UserRole.STAFF and not hospital_id:
        from app.models.hospital import Hospital
        test_hosp = db_session.query(Hospital).filter(Hospital.name == "Test Central Hospital").first()
        if test_hosp:
            hospital_id = test_hosp.id
        else:
            first_hosp = db_session.query(Hospital).first()
            if first_hosp:
                hospital_id = first_hosp.id

    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        if hospital_id and existing.hospital_id != hospital_id:
            existing.hospital_id = hospital_id
            db_session.flush()
        token = create_access_token(subject=str(existing.id), role=existing.role.value)
        headers = {"Authorization": f"Bearer {token}"}
        return existing, headers

    user = User(
        name=name,
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        hospital_id=hospital_id,
    )
    db_session.add(user)
    db_session.flush()
    token = create_access_token(subject=str(user.id), role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers
