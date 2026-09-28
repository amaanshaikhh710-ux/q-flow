# Q-FLOW — Queue State Machine

## Patient lifecycle
```text
BOOKED → ARRIVED → WAITING → CALLED → IN_CONSULTATION → COMPLETED
                     │
                     ├→ TEMPORARILY_LEFT → RETURNED → STAFF_REQUEUES → WAITING
                     └→ NO_SHOW
```

## States
- BOOKED: Appointment booked (online or phone), awaiting physical arrival at the hospital.
- ARRIVED: Patient physically arrived at the hospital OPD desk.
- WAITING: Checked-in and eligible for doctor service.
- CALLED: Staff has called patient to consultation room.
- IN_CONSULTATION: Clinical service started.
- COMPLETED: Clinical service completed and recorded.
- TEMPORARILY_LEFT: Patient temporarily unavailable (excluded from active call sequence).
- RETURNED: Patient returned; awaiting staff re-queueing.
- NO_SHOW: Staff recorded non-attendance.

## Queue states
- ACTIVE
- PAUSED
- COMPLETED

## Valid transitions
| From | Event | To | Notes |
|---|---|---|---|
| BOOKED | PATIENT_ARRIVED | ARRIVED | Staff marks physical arrival at OPD |
| ARRIVED | CHECKED_IN / PATIENT_WAITING | WAITING | Staff advances arrived patient into active waiting line |
| BOOKED | DIRECT_CHECK_IN (Walk-in) | WAITING | Walk-in patient arrives and checks in immediately |
| WAITING | PATIENT_CALLED | CALLED | Staff calls patient to room |
| CALLED | CONSULTATION_STARTED | IN_CONSULTATION | Clinical service begins; started_at recorded |
| IN_CONSULTATION | CONSULTATION_COMPLETED | COMPLETED | completed_at recorded; duration_seconds calculated |
| WAITING | PATIENT_TEMPORARILY_LEFT | TEMPORARILY_LEFT | Excluded from active queue call order |
| TEMPORARILY_LEFT | PATIENT_RETURNED | RETURNED | Returned to clinic |
| RETURNED | STAFF_REQUEUES | WAITING | Staff actively restores patient into WAITING |
| WAITING/CALLED/BOOKED | PATIENT_NO_SHOW | NO_SHOW | Marked absent; downstream ETAs recalculate |

## Temporary leave policy: STAFF-MANAGED RE-QUEUEING (FINAL)
When a patient temporarily leaves:
- Marked `TEMPORARILY_LEFT`; excluded from active calling sequence.
- When they return, marked `RETURNED`.
- Staff explicitly decides and executes `STAFF_REQUEUES` to return them to `WAITING`.
- No automatic position preservation and no automatic push to back of queue without staff action.
- Downstream predictions recalculate immediately upon leave and upon requeue.

## Invalid transitions
Examples: COMPLETED→WAITING without correction workflow; NO_SHOW→COMPLETED without reactivation; arbitrary patient queue reorder; TEMPORARILY_LEFT→COMPLETED without valid consultation flow. All invalid transitions are strictly rejected by the server with HTTP 409 Conflict.

## Queue Ordering & Priority Policy
The queue engine enforces deterministic server-side ordering for all active `WAITING` entries:
1. **Priority Rank**:
   - `EMERGENCY`: Rank 1 (Highest priority, placed ahead of all priority and normal patients)
   - `PRIORITY`: Rank 2 (Placed ahead of normal patients)
   - `NORMAL`: Rank 3 (Standard arrival order)
2. **Within same priority rank**: Ordered by arrival timestamp `joined_at ASC`, with `token_number ASC` as deterministic tie-breaker.
3. **Queue Positions**:
   - 1-indexed for `WAITING` entries (Position 1 is next to be called).
   - Position 0 for `CALLED` and `IN_CONSULTATION`.
   - `None` (null) for inactive entries (`TEMPORARILY_LEFT`, `RETURNED`, `NO_SHOW`, `COMPLETED`).
4. **Token Identity Decoupling**: Priority changes or emergency insertions never alter or renumber existing token numbers.

## Token Allocation & Concurrency Strategy
- **Token Format**: Integer stored internally, rendered as display token formatted with prefix (e.g., `Q001`, `Q002`).
- **Atomic Concurrency Strategy**: To eliminate race conditions during concurrent joins, the parent `Queue` row is locked inside the database transaction using `SELECT ... FOR UPDATE`.
- **Sequential Invariant**: Token number is computed as `coalesce(max(token_number), 0) + 1` within the locked transaction, guaranteeing strictly unique, incrementing tokens without duplicate keys even under simultaneous client join requests.
- **Duplicate Protection**: A patient cannot hold multiple concurrent active tickets (`WAITING`, `CALLED`, `IN_CONSULTATION`, `TEMPORARILY_LEFT`, `RETURNED`) in the same queue; attempts return HTTP 409 Conflict.

## Transaction Strategy & Event Store Auditability
- Every state mutation (join, call-next, consultation start, consultation complete, leave, return, requeue, priority change, emergency insertion, disruption) and its corresponding audit log row in `queue_events` execute inside the same atomic database transaction (`commit` or `rollback`).
- `queue_events` is strictly append-only: past operational events are never updated or deleted.
- Event payloads record actor user ID, previous state, new state, token display, and non-sensitive operational metadata.

## System Events
- `PATIENT_JOINED`: Patient joined active queue and received token.
- `PATIENT_CALLED`: Staff called patient to door.
- `CONSULTATION_STARTED`: Clinical consultation started; created record in `consultations` table.
- `CONSULTATION_COMPLETED`: Clinical consultation finished; recorded elapsed seconds in `consultations`.
- `PATIENT_NO_SHOW`: Patient recorded as absent.
- `PATIENT_TEMPORARILY_LEFT`: Staff/Admin marked patient temporarily away.
- `PATIENT_RETURNED`: Staff/Admin marked patient returned; awaiting staff requeue.
- `STAFF_REQUEUES`: Staff restored returned patient to active waiting order.
- `PRIORITY_CHANGED`: Priority rank updated for a waiting patient.
- `EMERGENCY_INSERTED`: Emergency patient inserted into active queue with top priority.
- `DOCTOR_DELAY`: Staff reported operational doctor delay with estimated minutes.
- `DOCTOR_BREAK_STARTED` / `DOCTOR_BREAK_ENDED`: Staff recorded doctor break interval.
- `QUEUE_PAUSED` / `QUEUE_RESUMED`: Operational pause/resume controls.

## Recalculation Triggers & Downstream Affected Entries
Every queue mutation that affects waiting sequence triggers `get_affected_downstream_entries(queue_id, from_position)`, returning the list of active entries whose positions changed to facilitate Phase 4 ETA reforecasting.
