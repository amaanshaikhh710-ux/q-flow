"""Inspect queue entries for today's date and show their linked Queue and DoctorSchedule."""
import os
import sys
from datetime import date
from pprint import pprint

# Ensure backend package root is importable when running this script from repo root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.database import SessionLocal
from app.models.queue_entry import QueueEntry
from app.models.queue import Queue
from app.models.doctor_schedule import DoctorSchedule
from app.services.queue_engine import QueueEngineService
from app.models.prediction_snapshot import PredictionSnapshot

SESSION = SessionLocal()

def inspect_for_date(target_date: date):
    print(f"Inspecting queue entries for date: {target_date.isoformat()}")
    q = SESSION.query(QueueEntry).filter(QueueEntry.appointment_date == target_date).order_by(QueueEntry.joined_at.desc()).limit(20).all()
    if not q:
        print("No queue entries found for that date.")
        return
    for e in q:
        print("-"*60)
        print(f"Entry ID: {e.id}")
        print(f" Queue ID: {e.queue_id}")
        print(f" Token: {e.token_number}")
        print(f" Appointment date: {e.appointment_date}")
        print(f" Schedule ID: {e.schedule_id}")
        print(f" Appointment time: {e.appointment_time}")
        print(f" Status: {e.status}")
        print(f" Joined at: {e.joined_at}")
        # Queue
        qrec = SESSION.query(Queue).filter(Queue.id == e.queue_id).one_or_none()
        if qrec:
            print(f" Queue.name: {qrec.name}")
            print(f" Queue.queue_date: {qrec.queue_date}")
            print(f" Queue.opd_session_id: {qrec.opd_session_id}")
        else:
            print(" Queue record not found")
        # Schedule
        if e.schedule_id:
            sched = SESSION.query(DoctorSchedule).filter(DoctorSchedule.id == e.schedule_id).one_or_none()
            if sched:
                print(" DoctorSchedule:")
                pprint({
                    "id": str(sched.id),
                    "doctor_id": str(sched.doctor_id),
                    "starts_at": str(sched.starts_at),
                    "ends_at": str(sched.ends_at),
                    "session_date": str(sched.session_date),
                })
            else:
                print(" DoctorSchedule not found")

if __name__ == '__main__':
    inspect_for_date(date(2026,9,23))
    print("\nNow showing the last 20 queue entries regardless of date:\n")
    recent = SESSION.query(QueueEntry).order_by(QueueEntry.joined_at.desc()).limit(20).all()
    if not recent:
        print("No queue entries in database at all.")
    else:
        for e in recent:
            print("-"*60)
            print(f"Entry ID: {e.id} | Appointment date: {e.appointment_date} | Queue ID: {e.queue_id} | Token: {e.token_number} | Status: {e.status}")
            qrec = SESSION.query(Queue).filter(Queue.id == e.queue_id).one_or_none()
            print(f" Queue found: {bool(qrec)} | Queue.queue_date: {qrec.queue_date if qrec else None}")
            try:
                pos = QueueEngineService.get_entry_position(SESSION, e)
                print(f" Server-authoritative position: {pos}")
            except Exception as ex:
                print(f" Could not compute position: {ex}")
            # If this is a BOOKED appointment, verify it appears in staff snapshot for same date
            if str(e.status) == 'QueueEntryStatus.BOOKED' or e.status == 'BOOKED':
                try:
                    snap = QueueEngineService.get_queue_snapshot(SESSION, e.queue_id, target_date=e.appointment_date)
                    booked_ids = [item.id for item in snap.get('booked_entries', [])]
                    appears = str(e.id) in booked_ids or e.id in booked_ids
                    print(f" Appears in staff snapshot booked_entries for {e.appointment_date}: {appears}")
                except Exception as ex:
                    print(f" Could not get snapshot for queue {e.queue_id} date {e.appointment_date}: {ex}")
            # Fetch latest prediction snapshot for this entry (if any)
            try:
                pred = (
                    SESSION.query(PredictionSnapshot)
                    .filter(PredictionSnapshot.queue_entry_id == e.id)
                    .order_by(PredictionSnapshot.created_at.desc())
                    .first()
                )
                if pred:
                    print(f" Latest prediction for entry {e.id}: start={pred.predicted_start_at} end={pred.predicted_end_at} uncertainty_min={pred.uncertainty_minutes}")
                    # Compare against schedule window if available
                    if qrec and qrec.opd_session_id:
                        sched = None
                        if e.schedule_id:
                            sched = SESSION.query(DoctorSchedule).filter(DoctorSchedule.id == e.schedule_id).first()
                        else:
                            sched = SESSION.query(DoctorSchedule).filter(DoctorSchedule.schedule_date == e.appointment_date, DoctorSchedule.doctor_id == qrec.opd_session.doctor_id if qrec.opd_session else None).first()
                        if sched:
                            print(f" Schedule window for date {e.appointment_date}: {sched.start_time} - {sched.end_time}")
                            # Check predicted_start_at within schedule window (convert prediction to IST)
                            try:
                                from datetime import timezone, timedelta
                                IST = timezone(timedelta(hours=5, minutes=30))
                                ps = pred.predicted_start_at
                                if ps:
                                    ps_ist = ps.astimezone(IST) if ps.tzinfo else ps.replace(tzinfo=timezone.utc).astimezone(IST)
                                    within = (ps_ist.time() >= sched.start_time) and (ps_ist.time() < sched.end_time)
                                    print(f" Predicted start (IST) = {ps_ist.time()} | within scheduled window: {within}")
                            except Exception:
                                pass
                else:
                    print(f" No prediction snapshot found for entry {e.id}")
            except Exception as ex:
                print(f" Could not fetch prediction for entry {e.id}: {ex}")

    print("\nDone.")
