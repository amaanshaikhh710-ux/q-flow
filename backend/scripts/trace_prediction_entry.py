"""Trace prediction generation for a specific QueueEntry ID for debugging.

Usage: run from repository root with the same env as other backend scripts.
"""
import os
import sys
from datetime import datetime

# Ensure backend package root is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.database import SessionLocal
import uuid
from app.models.queue_entry import QueueEntry
from app.models.queue import Queue
from app.models.doctor_schedule import DoctorSchedule
from app.models.consultation import Consultation
from app.models.queue_event import QueueEvent
from app.models.prediction_snapshot import PredictionSnapshot
from app.services.reforecast_service import PredictionService

SESSION = SessionLocal()

ENTRY_ID = "1111a488-9d24-4183-893e-b9ac93135f45"


def dump_entry(entry_id: str):
    print(f"Tracing entry {entry_id}")
    # ensure UUID type for comparison
    try:
        entry_uuid = uuid.UUID(entry_id)
    except Exception:
        entry_uuid = entry_id
    e = SESSION.query(QueueEntry).filter(QueueEntry.id == entry_uuid).first()
    if not e:
        print("Entry not found")
        return

    print("-- QueueEntry --")
    for k in ["id", "queue_id", "patient_user_id", "appointment_date", "appointment_time", "schedule_id", "status", "token_number", "joined_at", "arrived_at", "called_at"]:
        print(f"{k}: {getattr(e, k)}")

    q = SESSION.query(Queue).filter(Queue.id == e.queue_id).one_or_none()
    print("\n-- Queue --")
    if q:
        print(f"id: {q.id} name: {q.name} queue_date: {q.queue_date} opd_session_id: {q.opd_session_id}")
    else:
        print("Queue not found")

    print("\n-- DoctorSchedule (by schedule_id) --")
    if e.schedule_id:
        sched = SESSION.query(DoctorSchedule).filter(DoctorSchedule.id == e.schedule_id).one_or_none()
        print(sched)
    else:
        print("No schedule_id on entry")

    print("\n-- OPD session / schedules for doctor on appointment_date --")
    # attempt to find doctor via queue->opd_session
    opd_session = None
    try:
        opd_session = q.opd_session if q else None
    except Exception:
        opd_session = None

    if opd_session:
        print(f"OPD session id: {opd_session.id} doctor_id: {opd_session.doctor_id} starts_at: {opd_session.starts_at} ends_at: {opd_session.ends_at}")
    else:
        print("No OPD session linked to queue")

    print("\n-- DoctorSchedules matching doctor & date --")
    if opd_session:
        docs = SESSION.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == opd_session.doctor_id, DoctorSchedule.schedule_date == e.appointment_date).all()
        for s in docs:
            print(f"sched id: {s.id} start: {s.start_time} end: {s.end_time} session_date: {s.schedule_date}")
    else:
        print("Cannot query doctor schedules without opd_session")

    print("\n-- Queue Events for this entry --")
    events = SESSION.query(QueueEvent).filter(QueueEvent.queue_entry_id == e.id).order_by(QueueEvent.event_time.asc()).all()
    for ev in events:
        print(f"{ev.event_time} {ev.event_type} payload={ev.payload_json}")

    print("\n-- Consultations for this entry --")
    consults = SESSION.query(Consultation).filter(Consultation.queue_entry_id == e.id).all()
    for c in consults:
        print(f"Consultation id={c.id} started_at={c.started_at} completed_at={c.completed_at}")

    print("\n-- Prediction snapshots for this entry --")
    preds = SESSION.query(PredictionSnapshot).filter(PredictionSnapshot.queue_entry_id == e.id).order_by(PredictionSnapshot.created_at.asc()).all()
    for p in preds:
        print(f"snap id={p.id} created_at={p.created_at} predicted_start_at={p.predicted_start_at} predicted_end_at={p.predicted_end_at} trigger={p.trigger_event_id}")

    print("\n-- Live calculation using PredictionService.calculate_entry_prediction --")
    svc = PredictionService()
    calc = svc.calculate_entry_prediction(SESSION, e)
    for k, v in calc.items():
        print(f"{k}: {v}")


if __name__ == '__main__':
    dump_entry(ENTRY_ID)
