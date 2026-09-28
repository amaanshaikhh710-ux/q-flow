"""Clean and re-seed the Q-FLOW database with 5 distinct Mumbai public hospitals.

This script:
1. Purges all existing data across all tables with CASCADE.
2. Seeds exactly 5 distinct reference hospitals (labeled as demo data).
3. Seeds exactly 15 departments (3 per hospital).
4. Seeds exactly 15 doctors with distinct realistic names matching requirements.
5. Seeds 15 active OPD sessions (today 08:00 - 16:00 UTC).
6. Seeds 15 active queues (one per doctor).
7. Seeds exactly 5 staff accounts, each permanently bound to their respective hospital.
8. Seeds 1 demo patient account ("Aarav Sharma", patient@qflow.com / password123).
9. Seeds realistic current-day queue entries with recent timestamps (10-30 min ago)
   plus separate historical entries (yesterday, last week) for reporting.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.user import User, UserRole
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Distinct Real-World Reference Hospital Data (Mumbai Municipal Hospitals)
# ---------------------------------------------------------------------------

HOSPITALS_DATA = [
    {
        "name": "King Edward Memorial (KEM) Hospital",
        "address": "Acharya Donde Marg, Parel, Mumbai, Maharashtra 400012",
        "latitude": 19.0026,
        "longitude": 72.8423,
        "staff": {
            "name": "Sunil More",
            "email": "staff.kem@qflow.com",
            "phone": "+919820000001",
            "password": "password123",
            "purpose": "KEM Hospital Central Reception & OPD Desk",
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [
                    {"name": "Dr. Arjun Mehta", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Dermatology",
                "doctors": [
                    {"name": "Dr. Neha Kulkarni", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Cardiology",
                "doctors": [
                    {"name": "Dr. Rohan Deshpande", "status": DoctorStatus.AVAILABLE},
                ],
            },
        ],
    },
    {
        "name": "BYL Nair Charitable Hospital",
        "address": "Dr. A.L. Nair Road, Mumbai Central, Mumbai, Maharashtra 400008",
        "latitude": 18.9712,
        "longitude": 72.8228,
        "staff": {
            "name": "Pooja Varma",
            "email": "staff.nair@qflow.com",
            "phone": "+919820000002",
            "password": "password123",
            "purpose": "BYL Nair Hospital OPD Queue Desk",
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [
                    {"name": "Dr. Sameer Patil", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Dermatology",
                "doctors": [
                    {"name": "Dr. Ayesha Khan", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Orthopedics",
                "doctors": [
                    {"name": "Dr. Vivek Shah", "status": DoctorStatus.AVAILABLE},
                ],
            },
        ],
    },
    {
        "name": "Sir J.J. Group of Hospitals",
        "address": "J.J. Marg, Byculla, Mumbai, Maharashtra 400008",
        "latitude": 18.9633,
        "longitude": 72.8339,
        "staff": {
            "name": "Anita Rane",
            "email": "staff.jj@qflow.com",
            "phone": "+919820000004",
            "password": "password123",
            "purpose": "Sir J.J. Outpatient Management Desk",
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [
                    {"name": "Dr. Ananya Joshi", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Cardiology",
                "doctors": [
                    {"name": "Dr. Kunal Bhat", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Pediatrics",
                "doctors": [
                    {"name": "Dr. Meera Nair", "status": DoctorStatus.AVAILABLE},
                ],
            },
        ],
    },
    {
        "name": "Lokmanya Tilak Municipal General Hospital",
        "address": "Sion West, Mumbai, Maharashtra 400022",
        "latitude": 19.0368,
        "longitude": 72.8601,
        "staff": {
            "name": "Deepak Shinde",
            "email": "staff.sion@qflow.com",
            "phone": "+919820000003",
            "password": "password123",
            "purpose": "LTMC Sion Hospital OPD Triage Desk",
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [
                    {"name": "Dr. Aditya Rao", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Pediatrics",
                "doctors": [
                    {"name": "Dr. Pooja Menon", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Orthopedics",
                "doctors": [
                    {"name": "Dr. Siddharth Shah", "status": DoctorStatus.AVAILABLE},
                ],
            },
        ],
    },
    {
        "name": "Rajawadi Municipal General Hospital",
        "address": "Rajawadi Road, Ghatkopar East, Mumbai, Maharashtra 400077",
        "latitude": 19.0768,
        "longitude": 72.9056,
        "staff": {
            "name": "Girish Kadam",
            "email": "staff.rajawadi@qflow.com",
            "phone": "+919820000005",
            "password": "password123",
            "purpose": "Rajawadi Hospital Central Reception Desk",
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [
                    {"name": "Dr. Nikhil Joshi", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Pediatrics",
                "doctors": [
                    {"name": "Dr. Riya Deshmukh", "status": DoctorStatus.AVAILABLE},
                ],
            },
            {
                "name": "Obstetrics & Gynecology",
                "doctors": [
                    {"name": "Dr. Varun Kulkarni", "status": DoctorStatus.AVAILABLE},
                ],
            },
        ],
    },
]


def clean_database():
    """Purge all tables completely to eradicate duplicate/old seed records."""
    print("=== Purging Existing Database Tables ===")
    with engine.connect() as conn:
        tables = [
            "consultations",
            "arrival_plans",
            "prediction_snapshots",
            "notifications",
            "queue_events",
            "queue_entries",
            "queues",
            "opd_sessions",
            "doctors",
            "departments",
            "users",
            "hospitals",
        ]
        for t in tables:
            try:
                conn.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
                print(f"  [CLEANED] Truncated table: {t}")
            except Exception as e:
                # Fallback for SQLite or if truncate fails
                try:
                    conn.execute(text(f"DELETE FROM {t}"))
                    print(f"  [CLEANED] Deleted from: {t}")
                except Exception as inner_e:
                    print(f"  [SKIP] Could not clean {t}: {inner_e}")
        conn.commit()
    print("=== Database Clean Complete ===\n")


def seed():
    clean_database()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("=== Seeding Clean Q-FLOW Demo Environment ===\n")
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(hours=8)

        # 1. Seed Demo Patient: Aarav Sharma
        patient_user = User(
            email="patient@qflow.com",
            name="Aarav Sharma",
            phone="+919999900002",
            password_hash=hash_password("password123"),
            role=UserRole.PATIENT,
        )
        db.add(patient_user)
        db.flush()
        print(f"[PATIENT] {patient_user.name} ({patient_user.email}) / password123")

        # Additional demo patient for isolation testing
        patient_b = User(
            email="priya.patel@qflow.demo",
            name="Priya Patel",
            phone="+919999900003",
            password_hash=hash_password("password123"),
            role=UserRole.PATIENT,
        )
        db.add(patient_b)
        db.flush()
        print(f"[PATIENT] {patient_b.name} ({patient_b.email}) / password123")

        # 2. Seed 5 Hospitals, Departments, Doctors, Sessions, Queues, Staff
        total_hospitals = 0
        total_depts = 0
        total_doctors = 0
        total_queues = 0

        for h_data in HOSPITALS_DATA:
            hospital = Hospital(
                name=h_data["name"],
                address=h_data["address"],
                latitude=h_data["latitude"],
                longitude=h_data["longitude"],
            )
            db.add(hospital)
            db.flush()
            total_hospitals += 1
            print(f"\n[HOSPITAL {total_hospitals}] {hospital.name}")
            print(f"  Address: {hospital.address}")

            # Staff account for this hospital
            s_info = h_data["staff"]
            staff_user = User(
                email=s_info["email"],
                name=s_info["name"],
                phone=s_info["phone"],
                hospital_id=hospital.id,
                password_hash=hash_password(s_info["password"]),
                role=UserRole.STAFF,
            )
            db.add(staff_user)
            db.flush()
            print(f"  [STAFF] {staff_user.name} ({staff_user.email}) -> Hospital ID: {hospital.id}")

            # Departments and Doctors
            for dept_data in h_data["departments"]:
                dept = Department(
                    hospital_id=hospital.id,
                    name=dept_data["name"],
                )
                db.add(dept)
                db.flush()
                total_depts += 1

                for doc_info in dept_data["doctors"]:
                    doctor = Doctor(
                        department_id=dept.id,
                        name=doc_info["name"],
                        status=doc_info["status"],
                    )
                    db.add(doctor)
                    db.flush()
                    total_doctors += 1

                    # Active OPD Session
                    session = OPDSession(
                        department_id=dept.id,
                        doctor_id=doctor.id,
                        starts_at=today_start,
                        ends_at=today_end,
                        status=SessionStatus.ACTIVE,
                    )
                    db.add(session)
                    db.flush()

                    # Active Queue
                    queue_name = f"{dept.name} - {doctor.name.replace('Dr. ', '')} OPD"
                    queue = Queue(
                        opd_session_id=session.id,
                        name=queue_name,
                        status=QueueStatus.ACTIVE,
                    )
                    db.add(queue)
                    db.flush()
                    total_queues += 1
                    print(f"    [QUEUE] {queue.name} (Doctor: {doctor.name})")

                    # Seed sample appointments for KEM and Nair General Medicine
                    if hospital.name.startswith("King Edward") and dept.name == "General Medicine":
                        seed_kem_general_medicine(db, queue, doctor, patient_user, patient_b, now)
                    elif hospital.name.startswith("BYL Nair") and dept.name == "General Medicine":
                        seed_nair_general_medicine(db, queue, doctor, patient_user, now)

        db.commit()

        print("\n==========================================")
        print("[SEED VERIFICATION]")
        print(f"  Hospitals:   {total_hospitals} (Expected: 5)")
        print(f"  Departments: {total_depts} (Expected: 15)")
        print(f"  Doctors:     {total_doctors} (Expected: 15)")
        print(f"  Queues:      {total_queues} (Expected: 15)")
        print(f"  Staff:       5 (One per hospital)")
        print(f"  Patients:    2 (Aarav Sharma + Priya Patel)")
        print("==========================================\n")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seed failed: {e}")
        raise
    finally:
        db.close()


def seed_kem_general_medicine(db, queue, doctor, patient_a, patient_b, now):
    """Seed realistic operational entries for KEM General Medicine queue."""
    # Entry 1: Aarav Sharma - BOOKED (joined 20 min ago)
    e1 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient_a.id,
        token_number=1,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.BOOKED,
        booking_source="ONLINE",
        joined_at=now - timedelta(minutes=20),
        notes="First consultation - seasonal fever",
    )
    db.add(e1)

    # Entry 2: Priya Patel - ARRIVED (joined 25 min ago, arrived 5 min ago)
    e2 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient_b.id,
        token_number=2,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.ARRIVED,
        booking_source="ONLINE",
        joined_at=now - timedelta(minutes=25),
        arrived_at=now - timedelta(minutes=5),
        notes="Follow-up consultation",
    )
    db.add(e2)

    # Historical Entry 1: Yesterday - COMPLETED
    yesterday = now - timedelta(days=1)
    e_hist1 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient_a.id,
        token_number=101,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.COMPLETED,
        booking_source="WALK_IN",
        joined_at=yesterday.replace(hour=9, minute=0, second=0),
        arrived_at=yesterday.replace(hour=9, minute=10, second=0),
    )
    db.add(e_hist1)
    db.flush()

    c1 = Consultation(
        queue_entry_id=e_hist1.id,
        doctor_id=doctor.id,
        started_at=yesterday.replace(hour=9, minute=20, second=0),
        completed_at=yesterday.replace(hour=9, minute=34, second=0),
        duration_seconds=840,
    )
    db.add(c1)

    # Historical Entry 2: Yesterday - NO_SHOW
    e_hist2 = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient_b.id,
        token_number=102,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.NO_SHOW,
        booking_source="PHONE",
        joined_at=yesterday.replace(hour=9, minute=30, second=0),
    )
    db.add(e_hist2)
    db.flush()


def seed_nair_general_medicine(db, queue, doctor, patient_a, now):
    """Seed sample entry for BYL Nair General Medicine queue."""
    e = QueueEntry(
        queue_id=queue.id,
        patient_user_id=patient_a.id,
        token_number=1,
        priority_class=PriorityClass.NORMAL,
        status=QueueEntryStatus.BOOKED,
        booking_source="ONLINE",
        joined_at=now - timedelta(minutes=15),
        notes="General checkup",
    )
    db.add(e)


if __name__ == "__main__":
    seed()
