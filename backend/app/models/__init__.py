"""Models package exporting all entity models and Base metadata."""

from app.models.base import Base
from app.models.hospital import Hospital
from app.models.department import Department
from app.models.user import User, UserRole
from app.models.doctor import Doctor, DoctorStatus
from app.models.opd_session import OPDSession, SessionStatus
from app.models.queue import Queue, QueueStatus
from app.models.queue_entry import QueueEntry, PriorityClass, QueueEntryStatus
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent, QueueEventType
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.models.prediction_snapshot import PredictionSnapshot
from app.models.arrival_plan import ArrivalPlan
from app.models.otp_token import OTPToken
from app.models.doctor_availability import DoctorAvailability
from app.models.doctor_schedule import DoctorSchedule

__all__ = [
    "Base",
    "Hospital",
    "Department",
    "User",
    "UserRole",
    "Doctor",
    "DoctorStatus",
    "OPDSession",
    "SessionStatus",
    "Queue",
    "QueueStatus",
    "QueueEntry",
    "PriorityClass",
    "QueueEntryStatus",
    "Consultation",
    "QueueEvent",
    "QueueEventType",
    "Notification",
    "NotificationChannel",
    "NotificationStatus",
    "PredictionSnapshot",
    "ArrivalPlan",
    "OTPToken",
    "DoctorAvailability",
    "DoctorSchedule",
]

