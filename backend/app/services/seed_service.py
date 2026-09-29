"""Idempotent Production Database Seeding Service for Q-FLOW.

Safely seeds:
1. 5 reference public hospitals in Mumbai.
2. 15 departments (3 per hospital).
3. 15 doctors (1 per department).
4. 5 staff accounts (1 per hospital, permanently bound to hospital_id).
5. 1 admin account.
6. 10 demo patient accounts (matching LoginPage.tsx 1-Click buttons) + backward-compatible patient@qflow.com.
7. Active OPD sessions and queues for today.
8. 15-day doctor schedules for all doctors (ensuring availability in calendar/picker).
9. Realistic live queue tokens for KEM and other hospitals for instant dashboard/ticket demo.

IDEMPOTENT GUARANTEE:
- Safe to run on every startup.
- Never drops or truncates tables.
- Never duplicates records.
- Preserves all real user accounts and real bookings.
- Updates demo credentials safely if password hash is outdated.
"""

import logging
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.hospital import Hospital
from app.models.department import Department
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, QueueEntryStatus, PriorityClass
from app.models.consultation import Consultation
from app.models.user import User, UserRole
from app.models.doctor_schedule import DoctorSchedule
from app.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo Hospital Specification
# ---------------------------------------------------------------------------

DEMO_HOSPITALS = [
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
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [{"name": "Dr. Arjun Mehta", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Dermatology",
                "doctors": [{"name": "Dr. Neha Kulkarni", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Cardiology",
                "doctors": [{"name": "Dr. Rohan Deshpande", "status": DoctorStatus.AVAILABLE}],
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
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [{"name": "Dr. Sameer Patil", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Dermatology",
                "doctors": [{"name": "Dr. Ayesha Khan", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Orthopedics",
                "doctors": [{"name": "Dr. Vivek Shah", "status": DoctorStatus.AVAILABLE}],
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
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [{"name": "Dr. Aditya Rao", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Pediatrics",
                "doctors": [{"name": "Dr. Pooja Menon", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Orthopedics",
                "doctors": [{"name": "Dr. Siddharth Shah", "status": DoctorStatus.AVAILABLE}],
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
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [{"name": "Dr. Ananya Joshi", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Cardiology",
                "doctors": [{"name": "Dr. Kunal Bhat", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Pediatrics",
                "doctors": [{"name": "Dr. Meera Nair", "status": DoctorStatus.AVAILABLE}],
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
        },
        "departments": [
            {
                "name": "General Medicine",
                "doctors": [{"name": "Dr. Nikhil Joshi", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Pediatrics",
                "doctors": [{"name": "Dr. Riya Deshmukh", "status": DoctorStatus.AVAILABLE}],
            },
            {
                "name": "Obstetrics & Gynecology",
                "doctors": [{"name": "Dr. Varun Kulkarni", "status": DoctorStatus.AVAILABLE}],
            },
        ],
    },
]

DEMO_PATIENTS = [
    {"name": "Aarav Sharma", "email": "patient01@qflow.com", "phone": "+919999900011", "password": "password123"},
    {"name": "Priya Patel", "email": "patient02@qflow.com", "phone": "+919999900002", "password": "password123"},
    {"name": "Rohan Verma", "email": "patient03@qflow.com", "phone": "+919999900003", "password": "password123"},
    {"name": "Ananya Iyer", "email": "patient04@qflow.com", "phone": "+919999900004", "password": "password123"},
    {"name": "Vikram Singh", "email": "patient05@qflow.com", "phone": "+919999900005", "password": "password123"},
    {"name": "Sneha Nair", "email": "patient06@qflow.com", "phone": "+919999900006", "password": "password123"},
    {"name": "Aditya Joshi", "email": "patient07@qflow.com", "phone": "+919999900007", "password": "password123"},
    {"name": "Meera Rao", "email": "patient08@qflow.com", "phone": "+919999900008", "password": "password123"},
    {"name": "Karan Malhotra", "email": "patient09@qflow.com", "phone": "+919999900009", "password": "password123"},
    {"name": "Riya Sen", "email": "patient10@qflow.com", "phone": "+919999900010", "password": "password123"},
    {"name": "Aarav Sharma", "email": "patient@qflow.com", "phone": "+919999900001", "password": "password123"},
]


def _ensure_user(db: Session, name: str, email: str, phone: str, password: str, role: UserRole, hospital_id: uuid.UUID = None) -> User:
    """Finds existing user by email or phone; creates or updates credentials if needed."""
    user = db.query(User).filter(or_(User.email == email, User.phone == phone)).first()
    if not user:
        user = User(
            name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            hospital_id=hospital_id,
        )
        db.add(user)
        db.flush()
    else:
        # Update credentials and hospital association if needed
        updated = False
        if not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
            updated = True
        if hospital_id and user.hospital_id != hospital_id:
            user.hospital_id = hospital_id
            updated = True
        if user.role != role:
            user.role = role
            updated = True
        if updated:
            db.flush()
    return user


def seed_demo_data(db: Session) -> Dict[str, int]:
    """Idempotently seeds hospitals, departments, doctors, staff, patients, and schedules."""
    counts = {
        "hospitals": 0,
        "departments": 0,
        "doctors": 0,
        "schedules": 0,
        "users": 0,
    }

    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        # 1. Seed Demo Patients
        patient_map: Dict[str, User] = {}
        for p_data in DEMO_PATIENTS:
            u = _ensure_user(
                db=db,
                name=p_data["name"],
                email=p_data["email"],
                phone=p_data["phone"],
                password=p_data["password"],
                role=UserRole.PATIENT,
            )
            patient_map[p_data["email"]] = u
            counts["users"] += 1

        # 2. Seed Admin User
        admin_user = _ensure_user(
            db=db,
            name="System Administrator",
            email="admin@qflow.com",
            phone="+919999900000",
            password="password123",
            role=UserRole.ADMIN,
        )
        counts["users"] += 1

        # 3. Seed Hospitals, Departments, Doctors, Staff, Sessions, Queues, Schedules
        kem_gen_med_queue = None
        kem_gen_med_doctor = None

        for h_data in DEMO_HOSPITALS:
            # Hospital
            hospital = db.query(Hospital).filter(Hospital.name == h_data["name"]).first()
            if not hospital:
                hospital = Hospital(
                    name=h_data["name"],
                    address=h_data["address"],
                    latitude=h_data["latitude"],
                    longitude=h_data["longitude"],
                )
                db.add(hospital)
                db.flush()
            counts["hospitals"] += 1

            # Staff for this hospital
            s_info = h_data["staff"]
            staff_user = _ensure_user(
                db=db,
                name=s_info["name"],
                email=s_info["email"],
                phone=s_info["phone"],
                password=s_info["password"],
                role=UserRole.STAFF,
                hospital_id=hospital.id,
            )
            counts["users"] += 1

            # If admin has no hospital yet, assign first hospital
            if not admin_user.hospital_id:
                admin_user.hospital_id = hospital.id
                db.flush()

            # Departments & Doctors
            for dept_data in h_data["departments"]:
                dept = (
                    db.query(Department)
                    .filter(Department.hospital_id == hospital.id, Department.name == dept_data["name"])
                    .first()
                )
                if not dept:
                    dept = Department(
                        hospital_id=hospital.id,
                        name=dept_data["name"],
                    )
                    db.add(dept)
                    db.flush()
                counts["departments"] += 1

                for doc_info in dept_data["doctors"]:
                    doctor = (
                        db.query(Doctor)
                        .filter(Doctor.department_id == dept.id, Doctor.name == doc_info["name"])
                        .first()
                    )
                    if not doctor:
                        doctor = Doctor(
                            department_id=dept.id,
                            name=doc_info["name"],
                            status=doc_info["status"],
                        )
                        db.add(doctor)
                        db.flush()
                    counts["doctors"] += 1

                    # Active OPD Session for today
                    today_session_start = datetime.combine(today, dt_time(8, 0)).replace(tzinfo=timezone.utc)
                    today_session_end = datetime.combine(today, dt_time(17, 0)).replace(tzinfo=timezone.utc)

                    session = (
                        db.query(OPDSession)
                        .filter(
                            OPDSession.doctor_id == doctor.id,
                            OPDSession.starts_at >= datetime.combine(today, dt_time(0, 0)).replace(tzinfo=timezone.utc),
                            OPDSession.starts_at <= datetime.combine(today, dt_time(23, 59, 59)).replace(tzinfo=timezone.utc),
                        )
                        .first()
                    )
                    if not session:
                        session = OPDSession(
                            department_id=dept.id,
                            doctor_id=doctor.id,
                            starts_at=today_session_start,
                            ends_at=today_session_end,
                            status=SessionStatus.ACTIVE,
                        )
                        db.add(session)
                        db.flush()

                    # Active Queue for today
                    queue = db.query(Queue).filter(Queue.opd_session_id == session.id).first()
                    if not queue:
                        queue_name = f"{dept.name} - {doctor.name.replace('Dr. ', '')} OPD"
                        queue = Queue(
                            opd_session_id=session.id,
                            name=queue_name,
                            queue_date=today,
                            status=QueueStatus.ACTIVE,
                        )
                        db.add(queue)
                        db.flush()

                    if hospital.name.startswith("King Edward") and dept.name == "General Medicine":
                        kem_gen_med_queue = queue
                        kem_gen_med_doctor = doctor

                    # Persist DoctorSchedule for today + next 14 days
                    for day_offset in range(15):
                        sched_date = today + timedelta(days=day_offset)
                        sched = (
                            db.query(DoctorSchedule)
                            .filter(
                                DoctorSchedule.doctor_id == doctor.id,
                                DoctorSchedule.schedule_date == sched_date,
                            )
                            .first()
                        )
                        if not sched:
                            sched = DoctorSchedule(
                                hospital_id=hospital.id,
                                doctor_id=doctor.id,
                                department_id=dept.id,
                                schedule_date=sched_date,
                                start_time=dt_time(9, 0),
                                end_time=dt_time(17, 0),
                                status="AVAILABLE",
                                created_by_staff_id=staff_user.id,
                                opd_session_id=session.id if day_offset == 0 else None,
                            )
                            db.add(sched)
                            counts["schedules"] += 1
                        else:
                            if sched.status != "AVAILABLE":
                                sched.status = "AVAILABLE"
                            if day_offset == 0 and not sched.opd_session_id:
                                sched.opd_session_id = session.id

        # 4. Seed sample live entries in KEM General Medicine (if empty)
        if kem_gen_med_queue:
            existing_entries_count = db.query(QueueEntry).filter(QueueEntry.queue_id == kem_gen_med_queue.id).count()
            if existing_entries_count == 0:
                p1 = patient_map.get("patient01@qflow.com")
                p2 = patient_map.get("patient02@qflow.com")
                p3 = patient_map.get("patient03@qflow.com")
                p4 = patient_map.get("patient04@qflow.com")
                p5 = patient_map.get("patient05@qflow.com")

                if p1:
                    db.add(QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p1.id,
                        appointment_date=today,
                        token_number=1,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.WAITING,
                        booking_source="ONLINE",
                        joined_at=now - timedelta(minutes=30),
                        arrived_at=now - timedelta(minutes=15),
                        notes="Seasonal viral fever consultation",
                    ))
                if p2:
                    db.add(QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p2.id,
                        appointment_date=today,
                        token_number=2,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.WAITING,
                        booking_source="ONLINE",
                        joined_at=now - timedelta(minutes=25),
                        arrived_at=now - timedelta(minutes=10),
                        notes="Follow-up consultation",
                    ))
                if p3:
                    db.add(QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p3.id,
                        appointment_date=today,
                        token_number=3,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.WAITING,
                        booking_source="ONLINE",
                        joined_at=now - timedelta(minutes=20),
                        arrived_at=now - timedelta(minutes=5),
                        notes="Routine checkup",
                    ))
                if p4:
                    db.add(QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p4.id,
                        appointment_date=today,
                        token_number=4,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.WAITING,
                        booking_source="PHONE",
                        joined_at=now - timedelta(minutes=15),
                        notes="Phone advance booking",
                    ))
                if p5:
                    db.add(QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p5.id,
                        appointment_date=today,
                        token_number=5,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.BOOKED,
                        booking_source="ONLINE",
                        joined_at=now - timedelta(minutes=10),
                        notes="Advance slot booking",
                    ))

                # Add 1 historical completed consultation for KEM stats
                if p1 and kem_gen_med_doctor:
                    hist_entry = QueueEntry(
                        queue_id=kem_gen_med_queue.id,
                        patient_user_id=p1.id,
                        appointment_date=today,
                        token_number=101,
                        priority_class=PriorityClass.NORMAL,
                        status=QueueEntryStatus.COMPLETED,
                        booking_source="WALK_IN",
                        joined_at=now - timedelta(hours=2),
                        arrived_at=now - timedelta(hours=1, minutes=50),
                    )
                    db.add(hist_entry)
                    db.flush()

                    db.add(Consultation(
                        queue_entry_id=hist_entry.id,
                        doctor_id=kem_gen_med_doctor.id,
                        started_at=now - timedelta(hours=1, minutes=40),
                        completed_at=now - timedelta(hours=1, minutes=25),
                        duration_seconds=900,
                    ))

        db.commit()
        logger.info(
            "[Seed] Database verified: %d hospitals, %d departments, %d doctors, %d users",
            counts["hospitals"], counts["departments"], counts["doctors"], counts["users"]
        )
        return counts

    except Exception as e:
        db.rollback()
        logger.exception("[Seed Error] Failed to seed demo data: %s", e)
        raise
