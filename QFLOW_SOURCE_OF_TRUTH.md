# Q-FLOW — Source of Truth Documentation Package

Generated from the project planning conversation and the project research/specification source.



---

# Q-FLOW — Project Overview

## Identity
- Project: Q-FLOW
- Team: Initiator
- Domain: Healthcare & MedTech
- Problem Statement: The Waitlist Nobody Sees
- PS No.: CX0308
- Positioning: **A Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System.**

## Problem
OPD visits are difficult to plan because consultation timing changes with the live queue, service duration, priority insertions, doctor interruptions, no-shows and other operational events. Existing digital queues and wait-time products already provide tokens, queue progress, notifications and, in some cases, prediction/travel features. Therefore Q-FLOW is not defined as a token app, booking app, generic AI wait predictor, or Google Maps integration.

## Objective
Continuously forecast when a patient is likely to be consulted, represent uncertainty honestly as a time window, adapt to live queue events, combine the forecast with traffic-aware travel time, and recommend a useful departure/arrival window. Give OPD staff one control center for multiple doctors and concurrent queues.

## Target users
- Patients
- Attendants/families
- OPD Staff / Reception
- Hospital administrators

Doctors are service providers whose availability and consultation activity affect queues; the current architecture does **not** include a separate Doctor Dashboard.

## Core journey
**Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive**

## End-to-end flow
```text
Hospital
  ↓
OPD Staff / Reception Control Center
  ↓
Multiple doctors / concurrent queues
  ↓
Live queue events
  ↓
Q-FLOW queue state + prediction engine
  ↓
Patient-specific consultation window
  ↓
Traffic-aware travel time
  ↓
Departure / arrival optimization
  ↓
Web/PWA + WhatsApp + SMS
```

## Major capabilities
### Queue
- Multiple doctors and concurrent queues
- Token/join flow
- Live queue movement
- Event history

### Prediction
- Robust baseline when data is limited
- Historical service patterns
- Service-duration prediction
- Current-session/live correction
- Uncertainty-aware ETA windows
- Disruption-aware recalculation

### Events and edge cases
- Emergency/priority insertion
- Doctor delay/break/interruption
- Queue pause/resume
- No-show
- Temporary leave and return
- Unusually long consultations/outliers
- Queue slowdown/shock

### Arrival optimization
- Traffic-aware travel time through the agreed Google Routes API direction
- Recommended departure window
- Safe arrival window
- Objective concept: reduce physical waiting while controlling lateness risk

### Explainability and operations
- “Why did my ETA change?”
- Reception Control Center operational stats (MVP)
- Queue-health advanced analytics (POST-MVP)
- What-if simulation (POST-MVP)

### Notifications
- Web/PWA (WebSockets)
- SMS (required MVP; mock provider first, Twilio pluggable)
- WhatsApp (POST-MVP)

## Differentiation
Q-FLOW does not claim that individual pieces are globally new. Its proposed differentiation is the combination of dynamic patient-specific forecasting, live event-driven queue reconstruction, disruption/outlier classification, uncertainty-aware ETA ranges, traffic-aware arrival optimization, explainable ETA changes, multi-user OPD operations, and hospital operational intelligence.

## Explicit scope boundary
Out of scope for the current product: full EMR, prescriptions, insurance, payments, bed management, appointment marketplace, AI medical chatbot, disease prediction, a full medical-record platform, and a separate Doctor Dashboard.

## Implementation status
The conversation establishes a detailed plan, not completed software. No feature is COMPLETE unless implementation and tests later establish it.


---

# Q-FLOW — Requirements

## Status vocabulary
- REQUIRED: current requirement
- PLANNED: agreed direction, not implemented
- TBD: not sufficiently specified
- DECISION REQUIRED: team must choose before final implementation

## Functional requirements
1. Support multiple doctors and multiple concurrent OPD queues.
2. Provide an OPD Staff / Reception Control Center for authorized staff.
3. Allow staff to record next-patient, consultation start/completion, priority/emergency, pause/resume, doctor break/delay, no-show, temporary leave and return events.
4. Allow patients to join a queue and receive a token.
5. Show live queue state and patient-specific prediction.
6. Prefer consultation windows/ranges over false-precision single timestamps.
7. Recalculate affected predictions after meaningful queue events.
8. Integrate traffic-aware travel time as a module and calculate a departure/arrival window.
9. Provide meaningful ETA-change explanations.
10. Support SMS notifications; support WhatsApp as planned.
11. Maintain event history for reconstruction, audit and prediction data.
12. Classify unusually long consultations rather than blindly deleting them.

## Patient requirements
- Join queue / get token
- View token and queue status
- View people ahead where permitted
- View consultation window
- View travel/departure guidance when available
- Receive meaningful ETA changes
- Understand why an ETA changed
- Receive essential updates by SMS
- Use detailed Web/PWA interface
- Use WhatsApp if enabled

## OPD staff requirements
- View multiple doctors and queues
- Call next patient
- Start/end consultation
- Insert emergency/priority case
- Pause/resume queue
- Record doctor delay/break/interruption
- Mark no-show
- Record temporary leave/return
- View queue and prediction signals

## Queue requirements
Queue state must distinguish normal waiting, called, consultation, completed, no-show, temporary absence and priority class. Event history is authoritative for reconstruction; cached state is not sufficient by itself.

## Prediction requirements
- Robust baseline before sufficient historical data
- Service-duration prediction once data supports it
- Live session correction
- Emergency insertion handling
- Doctor delay/break handling
- No-show handling
- Long-consultation/outlier handling
- Multiple doctors/queues
- Uncertainty-aware windows

Progression: Phase 1 rolling median baseline $\rightarrow$ Phase 2 scikit-learn tabular model. The queue engine is decoupled from ML and works on the statistical baseline if ML is unavailable. Queue Shock Detector is POST-MVP.

## Notification requirements
Notify on meaningful changes rather than every small ETA movement. Meaningful-change threshold is set to >= 10 minutes (configurable). SMS is the primary external channel for MVP. Implemented via a notification abstraction with a local/mock provider for dev, and Twilio pluggable for production. WhatsApp is POST-MVP.

## Admin requirements
Planned advanced capabilities: advanced queue health analytics and what-if capacity simulation are POST-MVP. Basic operational monitoring is provided in the Reception Control Center.

## Non-functional requirements
- Real-time propagation of queue changes
- Server-authoritative queue state
- Auditable staff events
- Modular prediction service
- No fabricated performance claims
- Secure authentication/authorization
- Protected patient data
- Reconnect-safe real-time clients

## Security requirements
- Authenticated staff/admin operations (JWT bearer + bcrypt)
- Server-side authorization (Patient, Staff, Admin)
- Secure password handling
- No API secrets in frontend
- Protected patient data
- Audit trail for sensitive queue actions

## Explicitly out of scope
Full EMR, diagnosis, disease prediction, prescriptions, insurance, payments, bed management, appointment marketplace, medical chatbot, full hospital ERP, Doctor Dashboard.

## Finalized MVP decisions (Resolved)
PostgreSQL + SQLAlchemy + Alembic (JSONB); dedicated `consultations` table; JWT + bcrypt auth; staff-managed re-queueing for temporary leave; >= 10 min configurable notification threshold; mock notification provider (Twilio pluggable); two-stage prediction progression decoupled from queue engine.

## Post-MVP features (Deferred)
WhatsApp integration; Queue Shock Detector; What-If capacity simulation; advanced queue health analytics; attendant/family shared tracking view.


---

# Q-FLOW — User Roles and Permissions

## Roles
1. Patient
2. Attendant/Family Viewer (POST-MVP)
3. OPD Staff / Reception
4. Hospital Administrator
5. Backend/System Service

## Patient
**View:** own token, queue status, people ahead where allowed, consultation window, travel/departure guidance, notification history, ETA-change explanations.

**Create:** account, queue join, approved travel/location input, leave request.

**Update:** own permitted profile/travel/arrival state.

**Cannot:** reorder queue, insert emergency, pause queue, edit consultation records, modify another patient, overwrite prediction.

## Attendant / Family Viewer (POST-MVP)
Deferred to post-MVP. If implemented later, can view a patient’s shared queue/ETA information with explicit authorization. Cannot mutate queue state.

## OPD Staff / Reception
**View:** authorized hospital/departments, doctors, concurrent queues, queue entries, consultation state, event history and operational prediction signals.

**Create/control:** next patient, consultation start/completion, priority/emergency insertion, pause/resume, doctor delay/break, no-show, temporary leave/return, and staff requeue.

**Cannot:** directly fabricate model output, modify unrelated hospital data, or bypass event recording.

## Hospital Administrator
**View:** hospital-level queues, analytics, queue-health signals, model/evaluation information where exposed, and what-if simulation if implemented.

**Configure:** exact configuration permissions TBD.

**Cannot:** silently rewrite historical events.

## System service
Handles authentication, authorization enforcement, queue transitions, prediction, notification dispatch, WebSocket broadcasting, persistence and event logging.

## Doctor
Doctor is a domain entity whose availability and consultation events affect the queue. The current product has **no separate Doctor Dashboard**. Adding direct doctor controls requires a documented decision and updates to requirements/API/UI/changelog.


---

# Q-FLOW — System Architecture

## Architecture principle
Event-driven OPD queue forecasting with clear separation between authentication, queue state, event history, prediction, travel/arrival optimization, notifications, UI and persistence.

## High-level flow
```text
PATIENT → React/PWA → FastAPI → Queue/Business Logic → Q-FLOW Engine → PostgreSQL
                                   │                  │
                                   │                  ├→ Google Routes API
                                   │                  └→ Notification Service (Mock/Twilio)
                                   ↓
                              WebSockets

HOSPITAL STAFF → Reception Control Center → multiple doctors/queues → queue events → Q-FLOW Engine
```

## Hospital-side model
```text
Hospital
  └─ OPD Staff / Reception Control Center
       ├─ Doctor A → Queue A
       ├─ Doctor B → Queue B
       └─ Doctor C → Queue C
```
Staff, not doctors, are the current queue operators.

## Event flow
1. Staff/patient action reaches API.
2. API authenticates/authorizes.
3. Business logic validates current state.
4. Queue event is appended.
5. Current queue projection is updated.
6. Prediction recalculates affected entries.
7. Travel/arrival plan recalculates when needed.
8. WebSocket state update is broadcast.
9. Notification service evaluates meaningful-change rules (threshold >= 10 mins).

## Critical Architectural Rule: Decoupled ML
The queue engine MUST NOT depend on the ML model being available.
```text
Queue Event
    ↓
Queue State Machine
    ↓
Authoritative Queue State
    ↓
Prediction Engine
    ↓
Statistical baseline / ML
    ↓
Uncertainty Window
    ↓
Arrival Optimizer
    ↓
WebSocket + Notification
```
ML is a prediction component, NOT the source of truth for queue state. If ML is down or training data is low, fallback to statistical baseline (median) is automatic.

## Database
Finalized: PostgreSQL with SQLAlchemy ORM, Alembic migrations, and JSONB.
Entities: hospitals, departments, users, doctors, OPD sessions, queues, queue entries, **consultations** (dedicated normalized table), queue events (append-only audit store), and notifications. See `05_DATABASE_SCHEMA.md`.

## Authentication
Finalized for MVP: JWT bearer authentication, bcrypt password hashing, and server-side role authorization (Patient, Staff, Admin) enforced via FastAPI dependencies. Doctor Dashboard is excluded.

## Real-time
WebSockets are the agreed direction. Clients must be able to resynchronize from authoritative current state after reconnect.

## Travel
Google Maps Routes API is a planned traffic-aware travel module, not the central innovation.

## Deployment
Cloud deployment is planned. Vercel/Netlify + Render/Railway/AWS were discussed as options; final provider is DECISION REQUIRED.


---

# Q-FLOW — Database Schema

**Status:** FROZEN FOR MVP. Database engine: **PostgreSQL** with SQLAlchemy ORM, Alembic migrations, and JSONB.

## Relationship
```text
HOSPITAL → DEPARTMENT → DOCTOR → OPD_SESSION → QUEUE → QUEUE_ENTRY → CONSULTATION
                                                   └→ QUEUE_EVENT
```

## `hospitals`
Purpose: participating hospital.
- `id` BIGINT/UUID PK
- `name` VARCHAR NOT NULL
- `address` VARCHAR/TEXT
- `latitude` DECIMAL TBD
- `longitude` DECIMAL TBD
- `created_at`, `updated_at` TIMESTAMP

## `departments`
Purpose: OPD/department.
- `id` PK
- `hospital_id` FK → hospitals.id
- `name` VARCHAR NOT NULL
- timestamps
Index: `(hospital_id, name)`

## `users`
Purpose: application accounts.
- `id` PK
- `name` VARCHAR NOT NULL
- `phone` VARCHAR unique where required
- `email` VARCHAR unique where required
- `password_hash` VARCHAR; never plaintext (bcrypt)
- `role` VARCHAR/ENUM (patient/staff/admin)
- timestamps

## `doctors`
Purpose: doctor identity/availability.
- `id` PK
- `department_id` FK
- `name` VARCHAR NOT NULL
- `status` VARCHAR/ENUM (available/unavailable/break)
- timestamps

## `opd_sessions`
Purpose: operational session.
- `id` PK
- `department_id` FK
- `doctor_id` FK
- `starts_at`, `ends_at` TIMESTAMP
- `status` (scheduled/active/paused/completed/cancelled)
- timestamps
Index `(doctor_id, starts_at)`

## `queues`
Purpose: concurrent queue.
- `id` PK
- `opd_session_id` FK
- `name` VARCHAR
- `status` active/paused/completed
- `current_position` optional cache; never sole source of truth
- timestamps

## `queue_entries`
Purpose: patient participation.
- `id` PK
- `queue_id` FK
- `patient_user_id` FK → users.id
- `token_number` unique within queue/session
- `priority_class` normal/priority/emergency
- `status` state-machine value (CREATED, WAITING, CALLED, IN_CONSULTATION, COMPLETED, TEMPORARILY_LEFT, RETURNED, NO_SHOW)
- `joined_at` TIMESTAMP NOT NULL
- `called_at` nullable TIMESTAMP
- `temporary_left_at` nullable TIMESTAMP
- `returned_at` nullable TIMESTAMP
- `no_show_at` nullable TIMESTAMP
- timestamps
Indexes `(queue_id,status)`, `(queue_id,token_number)`, `(patient_user_id,created_at)`

*(Note: Consultation lifecycle start/end timestamps are normalized into the dedicated `consultations` table below).*

## `consultations`
Purpose: primary source of truth for clinical consultation records and durations.
- `id` PK (BIGINT/UUID)
- `queue_entry_id` FK → queue_entries.id UNIQUE NOT NULL
- `doctor_id` FK → doctors.id NOT NULL
- `started_at` TIMESTAMP NOT NULL
- `completed_at` TIMESTAMP nullable
- `duration_seconds` INT nullable (recorded upon completion)
- `interruption_notes` TEXT nullable
- `created_at`, `updated_at` TIMESTAMP
Indexes `(doctor_id, started_at)`, `(queue_entry_id)`

## `queue_events`
Purpose: append-only operational history, reconstruction, audit and model data.
- `id` PK
- `queue_id` FK
- `queue_entry_id` nullable FK
- `actor_user_id` nullable FK
- `event_type` VARCHAR/ENUM
- `event_time` TIMESTAMP
- `payload_json` JSONB
- `created_at`
Indexes `(queue_id,event_time)`, `(queue_entry_id,event_time)`, `(event_type,event_time)`

Event types include: TOKEN_CREATED, PATIENT_JOINED, PATIENT_CHECKED_IN, PATIENT_CALLED, CONSULTATION_STARTED, CONSULTATION_COMPLETED, PRIORITY_INSERTED, EMERGENCY_INSERTED, DOCTOR_BREAK_STARTED/ENDED, DOCTOR_DELAY, QUEUE_PAUSED/RESUMED, PATIENT_NO_SHOW, PATIENT_TEMPORARILY_LEFT, PATIENT_RETURNED, DOCTOR_UNAVAILABLE, DOCTOR_AVAILABLE.

## `notifications`
Purpose: delivery tracking.
- `id` PK
- `user_id` FK
- `queue_entry_id` nullable FK
- `channel` SMS/WHATSAPP/WEB
- `notification_type`
- `content_reference` or approved content fields
- `status` (pending/sent/delivered/failed)
- `sent_at`, `delivered_at`, `failed_at`
- `created_at`

## Consultation record decision: RESOLVED
Use a dedicated normalized `consultations` table as the primary source of truth for consultation records and timestamps. `queue_events` remains the append-only event/audit source.

## Business rules
1. Event history is retained.
2. Cached queue state is not the only source of truth.
3. Real long consultations are not erased from live state.
4. Emergency is a queue event/class, not merely an outlier.
5. No-show changes downstream ETA.
6. Doctor delay/break changes availability and ETA.
7. Queues have independent mutable state.
8. Authorization prevents cross-hospital access.
9. Cascade/delete policy is TBD and must be explicit before production migrations.


---

# Q-FLOW — API Specification

Exact routes were not finalized in the planning discussion. The following are the **proposed implementation contract** derived from the agreed requirements. If implementation changes a route, update this document and the changelog.

## Conventions
- Proposed base: `/api/v1`
- JSON over HTTPS
- Auth/role checks server-side
- Every staff queue mutation creates an event
- Validation at API boundary

## Auth
### POST `/auth/register`
Patient registration. Request: name, phone/email, password. Validation/provider policy TBD.

### POST `/auth/login`
Request: identifier + password. Returns session/access token and role.

### POST `/auth/logout`
Invalidates session where supported.

## Discovery
### GET `/hospitals`
List available hospitals.
### GET `/hospitals/{hospital_id}/departments`
List departments.
### GET `/departments/{department_id}/doctors`
List doctors/queues available for selection.

## Patient queue
### POST `/queues/{queue_id}/join`
Creates queue entry and token. Patient cannot self-escalate to emergency under current rules.

### GET `/queue-entries/{entry_id}`
Returns authoritative state, token, position, prediction and relevant arrival information.

### POST `/queue-entries/{entry_id}/leave`
Records temporary leave (status transitions to TEMPORARILY_LEFT). Excludes entry from active call sequence.

### POST `/queue-entries/{entry_id}/return`
Records patient return (status transitions to RETURNED). Awaits staff re-queueing.

### POST `/queue-entries/{entry_id}/arrival`
Records patient arrival/check-in.

## Staff
### GET `/staff/queues`
Returns authorized concurrent queues.

### POST `/staff/queues/{queue_id}/next`
Calls next eligible patient; creates event, updates state, recalculates and broadcasts.

### POST `/staff/queue-entries/{entry_id}/consultation/start`
Creates CONSULTATION_STARTED event and initializes a record in the dedicated `consultations` table with `started_at`.

### POST `/staff/queue-entries/{entry_id}/consultation/complete`
Creates CONSULTATION_COMPLETED event and finalizes the `consultations` record with `completed_at` and `duration_seconds`.

### POST `/staff/queues/{queue_id}/priority`
Request: priority class + reason. Creates priority/emergency event and recalculates affected entries.

### POST `/staff/queues/{queue_id}/pause` and `/resume`
Queue controls.

### POST `/staff/doctors/{doctor_id}/delay`
Records delay.

### POST `/staff/doctors/{doctor_id}/break/start` and `/break/end`
Records doctor break.

### POST `/staff/queue-entries/{entry_id}/no-show`
Marks no-show and recalculates downstream ETAs.

### POST `/staff/queue-entries/{entry_id}/temporary-leave` and `/return`
Staff-side recording of patient absence and return.

### POST `/staff/queue-entries/{entry_id}/requeue`
Staff explicitly re-queues a RETURNED patient into WAITING state. Triggers downstream ETA recalculation.

## Prediction
### GET `/queue-entries/{entry_id}/prediction`
Returns consultation window, uncertainty, people ahead where permitted, travel/departure data if available, and reason codes. No fabricated confidence.

### POST `/prediction/recalculate`
Internal/admin/dev operation for explicit recalculation/testing.

## Travel
### POST `/queue-entries/{entry_id}/travel-estimate`
Input: origin and relevant travel context. Backend calls Google Routes API. Exact location schema/storage is TBD.

### GET `/queue-entries/{entry_id}/arrival-plan`
Returns consultation window, travel window, recommended departure and safe arrival window.

## Notifications
### GET `/notifications`
Returns authorized notification history.
### POST `/notifications/test`
Development/admin only.

## WebSocket
Proposed: `WS /ws/queues/{queue_id}`. Authentication required. Example event:
```json
{"type":"QUEUE_UPDATED","queue_id":"id","version":123,"timestamp":"..."}
```
Prediction update:
```json
{"type":"PREDICTION_UPDATED","queue_entry_id":"id","prediction":{"start":"...","end":"..."},"reason_codes":["PRIORITY_INSERTED"]}
```
Exact payload schema TBD.

## Errors
Use 400 validation/business input, 401 unauthenticated, 403 unauthorized, 404 missing resource, 409 invalid state conflict, 422 schema validation where FastAPI conventions apply, 429 where rate limiting exists, 500 unexpected failure.

## API invariants
- Client cannot authoritatively reorder queues.
- Staff mutations create events.
- Prediction uses authoritative state.
- WebSocket broadcasts occur after successful state changes.
- Provider secrets never reach clients.


---

# Q-FLOW — Prediction Engine

## Purpose
Estimate when a specific patient is likely to be consulted, express uncertainty honestly, adapt to live queue conditions, and support travel-aware arrival optimization. No Q-FLOW accuracy claim is valid until measured.

## Four conceptual layers
### Model A — Service Duration
Predict consultation/service duration using available context. Features: doctor, department, day/time, priority class, queue length, current session speed, historical doctor speed.
Progression (FINAL FOR MVP):
- Phase 1: Robust statistical baseline using rolling/historical median service duration.
- Phase 2: Basic tabular service-duration model using scikit-learn.
Architecture allows later replacement with XGBoost/CatBoost without rewriting the queue engine.

**Critical Architectural Rule:** The queue engine MUST NOT depend on ML availability. If ML is unavailable or training data is insufficient, fallback to the robust statistical baseline is automatic.

### Model B — Queue State / Downstream ETA
Determine which eligible patients are ahead and accumulate service-time estimates while accounting for queue state and doctor availability.

### Model C — Disruption / Volatility
Incorporate emergency insertion, doctor delay/break, sudden slowdown, no-show and other recorded operational events. Do not claim to know that a future emergency will happen.

### Model D — Arrival Optimizer
Combine consultation window, travel-time estimate, buffer and lateness risk to recommend departure/arrival.

## Current position
Authoritative queue position comes from server-side queue state/event history, not token arithmetic in the browser.

Algorithmic sequence:
1. Identify eligible entries ahead.
2. Apply priority ordering (EMERGENCY > PRIORITY > NORMAL).
3. Exclude completed/no-show entries.
4. Exclude TEMPORARILY_LEFT entries (awaiting staff requeue).
5. Check doctor availability and queue pause.
6. Estimate service duration for relevant patients (scikit-learn or median baseline).
7. Accumulate expected downstream time.
8. Apply live correction/disruption logic.
9. Produce uncertainty bounds.

## Baseline
Before sufficient historical data, use robust statistics: rolling median and historical median doctor/department service duration.

## Cold start & fallback
```text
No/low data / ML down → robust median baseline → scikit-learn tabular model → live correction
```
Fallback to baseline is automatic and seamless.

## Live correction
Compare recent completed consultation durations with historical/session expectations. Faster current sessions should move forecasts accordingly; slower sessions should do the same.

## Emergency insertion
When staff records an emergency/priority case: append event → change queue ordering → recompute affected patients → produce reason code (`PRIORITY_INSERTED`) → broadcast → evaluate notification.

## Outliers
### Data error
Impossible timestamps/invalid records: reject or exclude from model training, while retaining audit/error information as appropriate.

### Operational anomaly
Example: doctor interruption causes unusually long service. Classify separately; do not treat as normal service baseline.

### Genuine complex consultation
Example: 40-minute clinical consultation. Retain; optionally classify.

### Emergency priority
A different queue class/event, not simply a statistical outlier.

**Critical rule:** outlier handling for forecasting is not pretending the event did not happen. The active queue uses actual elapsed/remaining time.

## Doctor delay/break
Recorded event changes availability and downstream ETA.

## No-show
Remove from eligible active path, retain event, recalculate downstream ETA.

## Temporary leave/return: STAFF-MANAGED RE-QUEUEING (FINAL)
When patient leaves, marked `TEMPORARILY_LEFT` (excluded from active service path). Upon return, marked `RETURNED`. Staff decides and executes `STAFF_REQUEUES` into `WAITING`. No automatic position preservation or end-of-queue placement.

## Multiple doctors
Each queue has independent state and service history. Hospital analytics may aggregate; mutable state must not leak across queues. Dynamic reassignment between doctors is POST-MVP.

## Queue shock detector: POST-MVP
Candidate behavior: monitor service-duration/queue-growth changes, detect sudden slowdown, widen uncertainty. Not a blocker for MVP; architecture allows adding post-MVP.

## ETA stability & notification threshold (FINAL FOR MVP)
Avoid notification noise from tiny fluctuations. Meaningful-change threshold is set to >= 10 minutes (configurable in backend settings). Outgoing notifications trigger only if window shifts >= 10 minutes or a critical event occurs.

## Explainable changes
Use reason codes such as PRIORITY_INSERTED, DOCTOR_DELAY, DOCTOR_BREAK, SERVICE_SPEED_CHANGE, NO_SHOW, QUEUE_PAUSED/RESUMED. Patient-facing text must reflect actual recorded/derived causes.

## Uncertainty
Preferred output:
```text
Expected consultation: 4:10–4:25 PM
```
Do not display a confidence percentage until interval calibration has actually been implemented and validated.

## Arrival optimization
Conceptual objective:
```text
expected wasted time = travel time + physical waiting time + lateness-risk penalty
```
Output: recommended departure window + safe arrival window. This objective is conceptual until implemented/tested.

## Evaluation
Use MAE, median absolute error, P90 absolute error, underestimation rate and prediction interval coverage. Never invent values.

## Benchmark
Model 0 simple average; Model 1 rolling median; Model 2 ML; Model 3 ML + live correction; Model 4 ML + live correction + disruption handling. Values must come from actual tests/simulation.

## Drift
Support monitoring/recalibration because service behavior can change. Retraining cadence TBD.


---

# Q-FLOW — Queue State Machine

## Patient lifecycle
```text
CREATED → WAITING → CALLED → IN_CONSULTATION → COMPLETED
             │
             ├→ TEMPORARILY_LEFT → RETURNED → STAFF_REQUEUES → WAITING
             └→ NO_SHOW
```

## States
- CREATED: entry exists but join/check-in is not complete.
- WAITING: eligible for service.
- CALLED: staff has called patient.
- IN_CONSULTATION: service started.
- COMPLETED: service ended.
- TEMPORARILY_LEFT: patient temporarily unavailable (excluded from active call sequence).
- RETURNED: patient returned; awaiting staff re-queueing.
- NO_SHOW: staff recorded non-attendance.

## Queue states
- ACTIVE
- PAUSED
- COMPLETED

## Valid transitions
| From | Event | To | Notes |
|---|---|---|---|
| CREATED | PATIENT_JOINED/CHECKED_IN | WAITING | Eligible for calling |
| WAITING | PATIENT_CALLED | CALLED | Staff calls patient |
| CALLED | CONSULTATION_STARTED | IN_CONSULTATION | Clinical service begins |
| IN_CONSULTATION | CONSULTATION_COMPLETED | COMPLETED | Record created in `consultations` |
| WAITING | PATIENT_TEMPORARILY_LEFT | TEMPORARILY_LEFT | Excluded from active queue call order |
| TEMPORARILY_LEFT | PATIENT_RETURNED | RETURNED | Returned to clinic |
| RETURNED | STAFF_REQUEUES | WAITING | Staff actively restores patient into WAITING |
| WAITING/CALLED | PATIENT_NO_SHOW | NO_SHOW | Marked absent; downstream ETAs recalculate |

## Temporary leave policy: STAFF-MANAGED RE-QUEUEING (FINAL)
When a patient temporarily leaves:
- Marked `TEMPORARILY_LEFT`; excluded from active calling sequence.
- When they return, marked `RETURNED`.
- Staff explicitly decides and executes `STAFF_REQUEUES` to return them to `WAITING`.
- No automatic position preservation and no automatic push to back of queue without staff action.
- Downstream predictions recalculate immediately upon leave and upon requeue.

## Invalid transitions
Examples: COMPLETED→WAITING without correction workflow; NO_SHOW→COMPLETED without reactivation; arbitrary patient queue reorder; TEMPORARILY_LEFT→COMPLETED without valid consultation flow. Return state-conflict errors.

## System events
- emergency/priority insertion
- doctor delay
- doctor break
- consultation start/completion
- doctor unavailable/available
- no-show
- temporary leave/return
- queue pause/resume

## Event record
Every important event should contain unique ID, timestamp, actor, queue, optional entry, type and structured payload.

## Recalculation triggers
Join, next patient, consultation start/completion, priority/emergency, delay/break, pause/resume, no-show, leave/return, queue shock and meaningful travel changes.

## Multiple queues
Each queue has independent lifecycle/state. Staff can see many queues together, but mutations are scoped to the target queue.


---

# Q-FLOW — UI/UX Specification

## Product visual direction
Use the established Q-FLOW visual language where appropriate: dark navy/black base, purple/blue/cyan neon accents, clean grid, large headings, rounded panels, meaningful diagrams/UI, minimal clutter. Usability takes priority over decorative effects.

## Patient screens
### Registration/Login
Identity, phone/email, password/auth, errors; SMS verification if chosen.

### Hospital Selection
Hospital list/search, address, relevant OPD availability.

### Department/Doctor/OPD Selection
Department, doctor, current queue/session status. Multiple doctors must be visible.

### Join Queue
Selected hospital/department/doctor, join action, token, applicable priority information. Patient cannot self-declare emergency under current assumptions.

### Live Queue
Token, people ahead where permitted, serving state, consultation window, last update, ETA-change reason, travel time, recommended departure/arrival window.

### ETA Explanation
Show only actual reasons, e.g. priority insertion, doctor interruption, service-speed change.

### Leave / Update
Temporary leave request and return instructions. Exact position policy TBD.

### Arrival / Check-in
Patient arrival action.

### Notifications
History and current updates from web/SMS/WhatsApp.

## Staff screens
### Login
Secure staff authentication.

### Reception Control Center
One control center showing multiple doctors/queues concurrently. Each queue needs serving token, waiting count, ETA and controls for next/priority/pause where authorized.

### Queue Detail
Ordered entries, status, priority, prediction, active events, event history.

### Patient Management
Call, start/complete consultation, no-show, temporary leave/return.

### Emergency Handling
Clear PRIORITY/EMERGENCY action with confirmation/reason capture if required.

### Doctor Delay/Break
Start/end break, delay, unavailable/available. All actions create events.

### Queue Health
If implemented: queue growth, service speed, ETA volatility, backlog, priority count. No fabricated score.

## Admin
Potential hospital configuration, analytics, queue health and what-if simulation. MVP scope TBD.

## Real-time UX
Queue changes update without full refresh. Reconnect must resynchronize from authoritative server state. Avoid noisy animation.

## Responsive
Patient UI: mobile-first PWA. Staff: desktop/tablet optimized.

## Accessibility
Readable contrast, non-color-only status, clear labels, practical keyboard support.

## Explicit UI rule
Do **not** create a separate Doctor Dashboard.


---

# Q-FLOW — User Flows

## Normal patient
```text
Open → Select hospital → Select department/doctor → Join queue → Get token
→ Monitor queue → Prediction updates → Departure guidance → Travel
→ Arrive/check in → Called → Consultation → Completed
```

## Temporary leave (Staff-Managed Re-queueing)
```text
WAITING → leave request/event → TEMPORARILY_LEFT (excluded from call sequence)
→ queue continues → patient returns → RETURNED → staff executes STAFF_REQUEUES → WAITING
→ ETA recalculated
```
Staff decides and executes re-queueing. No automatic position preservation or pushing to back of queue.

## Emergency
Staff records priority/emergency → backend validates → event stored → queue ordering changes → affected predictions recalculate → WebSocket updates → notification decision.

## Doctor delay
Staff records delay/break → doctor availability changes → queue progression affected → ETA recalculated → affected patients updated.

## Long consultation
Consultation starts → actual elapsed time becomes live queue state → divergence from expected service detected → live correction/uncertainty adjusts → classifier labels if appropriate → completed event stores actual duration in `consultations` and `queue_events`. Training treatment differs by classification.

## No-show
Patient does not respond → staff marks NO_SHOW → event stored → patient removed from active service path → downstream ETA recalculated.

## Multiple doctors
```text
Hospital
 ├─ Doctor A → Queue A
 ├─ Doctor B → Queue B
 └─ Doctor C → Queue C
```
Staff operates authorized queues from one control center.

## Queue completion
Last eligible patient completes → session/queue completes → new joins disabled → history retained → patient sees completed state.

## ETA change
```text
Event → recalculate → compare old/new → shift >= 10 minutes?
                         ├─ no (<10 min)  → UI update (WebSockets)
                         └─ yes (>=10 min) → trigger notification abstraction (SMS/mock)
```

## Travel update
Patient supplies/permits origin → travel request → Google Routes API → travel interval → arrival optimizer → departure window → patient update.


---

# Q-FLOW — Notification System

## Channels
- Web/PWA real-time updates (WebSockets)
- **SMS — PRIMARY REQUIRED for MVP**
- **WhatsApp — POST-MVP**

## Provider architecture (FINAL FOR MVP)
- Core service interacts with an abstract notification interface (`NotificationProvider`).
- Development uses a **local/mock provider** that records and logs messages.
- Production/external gateway allows plugging in **Twilio** without altering queue or prediction logic.

## Meaningful-change threshold (FINAL FOR MVP)
Do not notify on small ETA movements. 
- **Threshold:** $\ge 10$ minutes change in the predicted consultation window (or explicit critical event).
- Threshold is **configurable in backend settings** rather than hardcoded.
- Trivial fluctuations do NOT trigger external notifications.

## Events
### Queue joined
Confirm token and initial ETA.

### ETA changed
If meaningful, show old/new window and reason where appropriate.

### Emergency/priority
Notify affected patients if their ETA meaningfully changes.

### Doctor delay/break
Notify when it materially affects the patient.

### Queue resumed
Notify where relevant.

### Recommended departure
Send departure window after queue + travel calculation is available.

### Arrival window changed
Send when queue/traffic changes materially affect the recommendation.

## SMS example
```text
Q-FLOW: Token 47. Est. consultation 4:10–4:25 PM. Recommended departure 3:30–3:40 PM.
```
This is an illustrative format only; final templates are TBD.

## WhatsApp
Can provide richer information: token, people ahead, consultation window, departure window and change reasons. Provider/template requirements TBD.

## Delivery flow
```text
Event → prediction → compare → meaningful? → select channel → send → record delivery state
```

## Failure handling
Notification failure must not block queue progression. Record failure and retry under provider-safe policy. Retry count/backoff TBD.

## Privacy
Do not put unnecessary medical information into SMS/WhatsApp. Q-FLOW does not require full medical records in the current scope.


---

# Q-FLOW — Technology Stack

## Finalized MVP Stack
| Layer | Technology | Status |
|---|---|---|
| Frontend | React + Tailwind CSS | FINAL FOR MVP |
| Backend | Python + FastAPI | FINAL FOR MVP |
| Database | PostgreSQL + SQLAlchemy ORM + Alembic (JSONB) | FINAL FOR MVP |
| Real-time | WebSockets | FINAL FOR MVP |
| Prediction Engine | Phase 1: Rolling median baseline<br>Phase 2: scikit-learn tabular model | FINAL FOR MVP (Decoupled from queue engine) |
| Travel Module | Google Maps Routes API | FINAL FOR MVP |
| Authentication | JWT bearer + bcrypt + FastAPI roles (Patient/Staff/Admin) | FINAL FOR MVP |
| SMS Notifications | Notification abstraction + Local/Mock provider (Twilio pluggable) | FINAL FOR MVP |
| WhatsApp | Deferred | POST-MVP |
| Queue Shock Detector | Deferred | POST-MVP |
| What-If Simulation | Deferred | POST-MVP |
| Frontend Deployment | Vercel / Netlify (Cloud) / Local | NON-BLOCKING FOR LOCAL DEV |
| Backend Deployment | Render / Railway / AWS / Local | NON-BLOCKING FOR LOCAL DEV |

## Architecture
```text
React/Tailwind → FastAPI → queue/event services → prediction engine → PostgreSQL
                                       │                │
                                       ├→ WebSockets     ├→ Google Routes API
                                       └→ notifications  └→ Mock / Twilio Provider
```

## Development workflow
Antigravity/Y-coding is the AI coding workflow. It is not a runtime stack component.


---

# Q-FLOW — AI Coding Rules for Antigravity / Y-Coding

## Source of truth
Treat `/docs` as authoritative. Before coding, read the relevant docs and current repository.

## Non-negotiable rules
1. Do not invent features, statistics, APIs, integrations or performance.
2. Do not silently change requirements.
3. Do not silently remove features.
4. Do not create duplicate functionality.
5. Do not create a Doctor Dashboard.
6. Preserve the Reception Control Center.
7. Preserve multiple doctors and concurrent queues.
8. Keep prediction logic separate and testable.
9. Queue state must be server-authoritative.
10. Staff queue mutations create events.
11. Never claim untested prediction accuracy.
12. Never delete genuine long consultations from live state.
13. Do not treat emergency as a generic outlier.
14. Do not predict a future emergency as fact.
15. Do not expose API secrets to frontend.
16. Do not mark unimplemented work COMPLETE.
17. Update schema documentation before/with schema changes.
18. Preserve historical changelog entries.
19. Update docs after meaningful changes.
20. If requirements conflict, flag the conflict instead of guessing.

## Required workflow
**ANALYZE → PLAN → IMPLEMENT → TEST → DOCUMENT → UPDATE CHANGELOG → UPDATE CURRENT PROJECT STATE**

### ANALYZE
Inspect `/docs`, repository, existing code, dependencies, affected requirements, conflicts and TBD decisions.

### PLAN
State files/modules, DB/API/UI effects and tests before implementation.

### IMPLEMENT
Respect boundaries: API validates, queue service mutates state/events, prediction consumes authoritative state, WebSockets broadcast successful changes, notifications are downstream.

### TEST
Test affected behavior and edge cases: emergency, long consultation, no-show, delay/break, leave/return, multiple doctors, pause/resume and low-data prediction.

### DOCUMENT
Update relevant docs after implementation.

### CHANGELOG
Append ADDED/CHANGED/REMOVED/FIXED/DATABASE/API/UI/SECURITY/TESTING/OTHER entries. Never rewrite history.

### CURRENT STATE
Only mark COMPLETE when code, integration, tests and documentation are complete.

## Conflict rule
If code and docs disagree: check latest decision; if unresolved, mark DECISION REQUIRED and stop the conflicting change rather than inventing a resolution.

## Database rule
No “just in case” tables/columns. Any schema change needs migration + docs + changelog.

## API rule
Every endpoint needs auth, validation, response/error behavior and business logic documentation.


---

# Q-FLOW — Changelog

Historical entries are preserved. Append new entries; do not delete history.

## Initial project decisions
### ADDED
- Q-FLOW positioned as a Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System.
- Multiple doctors and multiple concurrent queues.
- Reception/OPD Staff Control Center.
- Patient journey: Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive.
- SMS notifications and planned WhatsApp/Web updates.
- Dynamic service-time prediction + live correction.
- Uncertainty-aware consultation windows.
- Emergency/priority insertion handling.
- Outlier classification: data error, operational anomaly, genuine complex consultation, emergency priority.
- No-show and doctor-delay/break handling.
- Temporary leave/return state.
- Queue shock detection concept.
- ETA stability concept.
- “Why did my ETA change?” explainability.
- Queue health and what-if simulation as advanced capabilities.
- Traffic-aware arrival optimization using Google Routes API direction.
- Event history for reconstruction/audit/model development.
- FastAPI + WebSockets direction.
- React + Tailwind direction.

### CHANGED
- Separate Doctor Dashboard was removed; Reception Control Center is the current hospital-side interface.
- Google Maps was repositioned from an apparent central idea to one travel-time module.
- Exact point ETA was replaced by uncertainty-aware windows.

### REMOVED
- Standalone Doctor Dashboard from current architecture.
- Claims that digital token/live queue alone is novel.
- Claims that leave-home notification alone differentiates Q-FLOW.

### FIXED
- Project positioning was refined to distinguish it from existing token/queue and ML wait-prediction systems.

### DATABASE
- Proposed entities: hospitals, departments, users, doctors, OPD sessions, queues, queue entries, queue events, notifications.
- MySQL/PostgreSQL remains unresolved.

### API
- FastAPI/WebSocket direction established; exact route names proposed but not historically locked.

### UI/UX
- Patient PWA/Web dashboard plus staff control center.
- Multiple doctors/queues must be visible to staff.

### SECURITY
- Auth/authorization, secure passwords and server-side enforcement required.

### TESTING
- Evaluation metrics planned: MAE, median absolute error, P90 absolute error, underestimation rate, prediction interval coverage.
- No Q-FLOW performance numbers are currently validated.

### OTHER
- Outlier handling must not erase live operational reality.
- Q-FLOW scope excludes EMR, payments, prescriptions, insurance, bed management, marketplace, disease prediction and medical chatbot.

## Final MVP decisions freeze (Initiator Hackathon MVP)
### ADDED
- Dedicated normalized `consultations` table for clinical service durations and lifecycle tracking.
- Staff-managed re-queueing policy for temporary leave (`WAITING -> TEMPORARILY_LEFT -> RETURNED -> STAFF_REQUEUES -> WAITING`).
- Pluggable `NotificationProvider` abstraction with local/mock provider for development.
- Configurable meaningful-change ETA notification threshold set to >= 10 minutes.
- Explicit decoupled prediction pipeline: Phase 1 rolling median baseline $\rightarrow$ Phase 2 scikit-learn tabular model.
- Decoupling rule: Queue engine functions even if ML model is unavailable.
- Implementation readiness checklist in `17_IMPLEMENTATION_READINESS_CHECK.md`.

### CHANGED
- Database engine resolved to PostgreSQL with SQLAlchemy ORM, Alembic migrations, and JSONB.
- Authentication resolved to JWT bearer tokens with bcrypt hashing and FastAPI server-side role authorization.
- Primary external notification channel for MVP locked to SMS (mock/Twilio).
- `queue_entries` schema updated: consultation start/complete timestamps normalized into `consultations`.

### POST-MVP
- WhatsApp integration deferred to Post-MVP.
- Queue Shock Detector deferred to Post-MVP.
- What-If Capacity Simulation deferred to Post-MVP.
- Advanced Hospital Queue-Health Analytics deferred to Post-MVP.
- Attendant / Family Viewer shared tracking view deferred to Post-MVP.
- Dynamic cross-doctor queue reassignment deferred to Post-MVP.

### FIXED
- Resolved temporary-leave ambiguity: explicit staff-controlled requeueing replaces automatic placement.
- Resolved consultation record ambiguity: dedicated `consultations` table created; `queue_events` remains audit log.

## Future entry format
### ADDED
### CHANGED
### REMOVED
### FIXED
### DATABASE
### API
### UI/UX
### SECURITY
### TESTING
### OTHER


---

# Q-FLOW — Current Project State

## Overall
**PLANNED / DOCUMENTATION READY** — detailed planning is established; implementation is not established by the conversation.

## Frontend — PLANNED
React + Tailwind; patient PWA/Web and Reception Control Center. Not implemented in this source record.

## Backend — PLANNED
Python + FastAPI; queue/event business logic. Not implemented in this source record.

## Database — FROZEN FOR MVP
Schema proposed. PostgreSQL chosen with SQLAlchemy ORM, Alembic migrations, and PostgreSQL JSONB. Dedicated `consultations` table adopted for consultation lifecycle tracking.

## Prediction engine — FROZEN FOR MVP
Two-stage progression:
- Phase 1: Robust statistical baseline (rolling/historical median).
- Phase 2: Basic tabular service-duration model using scikit-learn.
Queue engine is decoupled from ML and functions with statistical baseline if ML is unavailable. Queue Shock Detector is POST-MVP.

## Authentication — FROZEN FOR MVP
JWT bearer authentication + bcrypt password hashing + FastAPI server-side role authorization (Patient, Staff, Admin). Doctor Dashboard is explicitly excluded.

## Notifications — FROZEN FOR MVP
Notification abstraction interface with local/mock provider first; Twilio pluggable for production. SMS is primary external channel for MVP. WhatsApp is POST-MVP. ETA notification threshold set to >= 10 minutes (configurable).

## Staff control center — PLANNED (MVP CORE)
Multi-doctor, multi-queue Reception Control Center with emergency, delay/break, no-show, and staff-managed leave/re-queue controls.

## Patient flow — PLANNED (MVP CORE)
Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive.

## Queue state machine — FROZEN FOR MVP
States/transitions documented. Temporary-leave policy finalized as Staff-Managed Re-queueing (`WAITING -> TEMPORARILY_LEFT -> RETURNED -> STAFF_REQUEUES -> WAITING`).

## API — PLANNED (MVP CONTRACT)
FastAPI direction established; route contract covers auth, discovery, patient queue, staff controls, prediction, travel, and WebSockets.

## Testing — PLANNED
Primary MVP acceptance test: End-to-end emergency insertion flow with downstream recalculation, WebSocket broadcast, and mock notification dispatch.

## Security — FROZEN FOR MVP
JWT bearer auth, server-side role authorization, bcrypt hashing, secret protection, patient data privacy, and append-only event audit trail.

## Cloud — PLANNED / NON-BLOCKING FOR LOCAL DEV
Cloud deployment intended (Vercel/Netlify + Render/Railway/AWS); local development takes priority.

## Performance — TBD
No fabricated Q-FLOW accuracy/MAE claims.

## Frozen MVP Decisions (Resolved)
1. Database: PostgreSQL + SQLAlchemy + Alembic + JSONB
2. Consultation storage: Dedicated `consultations` table
3. Authentication: JWT bearer + bcrypt + FastAPI roles
4. Temporary-leave policy: Staff-managed re-queueing
5. Notification abstraction: Local/mock provider first, Twilio pluggable
6. ETA notification threshold: >= 10 minutes (configurable)
7. Prediction progression: Phase 1 median baseline $\rightarrow$ Phase 2 scikit-learn tabular model
8. Decoupled ML: Queue engine does not depend on ML availability
9. Interface: Reception Control Center for staff; no Doctor Dashboard

## Post-MVP Features (Deferred)
1. Queue Shock Detector
2. WhatsApp Integration
3. What-If Capacity Simulation
4. Advanced Hospital Queue-Health Analytics
5. Attendant / Family Shared Tracking View
6. Dynamic patient reassignment between doctors


---

# Q-FLOW — Decision Log

## DEC-001 — Product positioning
**Decision:** Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization System.
**Reason:** Digital queues, leave-home alerts, ML wait prediction and travel-time combinations already exist individually.
**Status:** ACCEPTED

## DEC-002 — Multiple doctors
**Decision:** Support multiple doctors and concurrent OPD queues.
**Reason:** Required for realistic OPD operations.
**Status:** ACCEPTED

## DEC-003 — Reception Control Center
**Decision:** OPD Staff / Reception Control Center replaces separate Doctor Dashboard.
**Reason:** Staff manages next patient, emergency insertion, breaks, delays, no-shows and other queue events.
**Status:** ACCEPTED; old Doctor Dashboard concept SUPERSEDED.

## DEC-004 — Patient journey
**Decision:** Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive.
**Status:** ACCEPTED

## DEC-005 — SMS
**Decision:** SMS is a required notification channel.
**Reason:** Basic-phone support.
**Status:** ACCEPTED

## DEC-006 — Web/PWA + WhatsApp
**Decision:** Detailed interface is Web/PWA. SMS is the primary external channel for MVP. WhatsApp is POST-MVP.
**Status:** ACCEPTED / FINAL FOR MVP (WhatsApp: POST-MVP)

## DEC-007 — Uncertainty-aware ETA
**Decision:** Use time windows rather than false-precision single times.
**Status:** ACCEPTED

## DEC-008 — Emergency
**Decision:** Known emergencies are explicit queue events; future emergencies are not predicted as certain.
**Status:** ACCEPTED

## DEC-009 — Outliers
**Decision:** Classify data errors, operational anomalies, genuine complex consultations and emergency priority separately.
**Reason:** Do not delete clinically real long consultations; do not confuse emergency class with statistical outlier.
**Status:** ACCEPTED

## DEC-010 — Live state vs training outlier handling
**Decision:** Excluding an event from a training baseline does not erase it from live queue state.
**Status:** ACCEPTED

## DEC-011 — Live correction
**Decision:** Adjust predictions using current session behavior.
**Status:** ACCEPTED conceptually

## DEC-012 — ETA stability & notification threshold
**Decision:** Avoid notification noise from small ETA changes. Use a meaningful ETA change threshold of >= 10 minutes. Only trigger outgoing notification if window shifts >= 10 minutes or critical event occurs. Keep threshold configurable in backend settings.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-013 — Queue shock detector
**Decision:** Detect sudden queue slowdown/volatility. Architecture allows adding later.
**Status:** POST-MVP (not a blocker for MVP)

## DEC-014 — ETA explanation
**Decision:** Provide “Why did my ETA change?” using actual recorded/derived reasons.
**Status:** ACCEPTED

## DEC-015 — Queue health
**Decision:** Hospital-side advanced queue health/operational intelligence. Basic operational information required by Reception Control Center is in MVP; advanced analytics is POST-MVP.
**Status:** POST-MVP for advanced analytics; Reception Control Center operational stats in MVP

## DEC-016 — What-if simulation
**Decision:** Advanced capacity simulation (e.g. adding another doctor).
**Status:** POST-MVP

## DEC-017 — Arrival optimization
**Decision:** Calculate recommended departure/safe arrival windows from consultation timing + travel time + risk/buffer.
**Status:** ACCEPTED conceptually

## DEC-018 — Google Maps role
**Decision:** Google Routes is a travel module, not the central innovation.
**Status:** ACCEPTED

## DEC-019 — Event history
**Decision:** Preserve explicit queue event history.
**Status:** ACCEPTED

## DEC-020 — Real-time
**Decision:** WebSockets for live queue/prediction updates.
**Status:** ACCEPTED direction

## DEC-021 — Backend
**Decision:** Python + FastAPI.
**Status:** ACCEPTED direction

## DEC-022 — Frontend
**Decision:** React + Tailwind.
**Status:** ACCEPTED direction

## DEC-023 — Database
**Decision:** PostgreSQL. Use SQLAlchemy ORM, Alembic migrations, and PostgreSQL JSONB where appropriate.
**Status:** ACCEPTED / FINAL FOR MVP (supersedes previous DECISION REQUIRED)

## DEC-024 — ML model progression & queue decoupling
**Decision:** Two-stage progression:
- Phase 1: Robust statistical baseline using rolling/historical median service duration.
- Phase 2: Basic tabular service-duration model using scikit-learn.
Architecture must decouple queue engine from ML so it works even if ML is down or data is sparse. Later replacement with XGBoost/CatBoost must not rewrite queue logic.
**Status:** ACCEPTED / FINAL FOR MVP (supersedes previous DECISION REQUIRED)

## DEC-025 — Performance claims
**Decision:** No fabricated Q-FLOW accuracy/performance.
**Status:** ACCEPTED

## DEC-026 — Evaluation metrics
**Decision:** MAE, median absolute error, P90 absolute error, underestimation rate, prediction interval coverage.
**Status:** ACCEPTED

## DEC-027 — Cold start
**Decision:** Robust/statistical baseline before ML is sufficiently supported by data.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-028 — Scope boundary
**Decision:** Do not expand into EMR, payments, prescriptions, insurance, bed management, marketplace, disease prediction or medical chatbot.
**Status:** ACCEPTED

## DEC-029 — Deployment
**Decision:** Cloud deployment intended; Vercel/Netlify + Render/Railway/AWS discussed.
**Status:** DECISION REQUIRED

## DEC-030 — Documentation authority
**Decision:** `/docs` is source of truth for Antigravity/Y-coding.
**Status:** ACCEPTED

## DEC-031 — Dedicated consultation storage
**Decision:** Use a dedicated normalized `consultations` table as the primary source of truth for consultation records and timestamps (`id`, `queue_entry_id`, `doctor_id`, `started_at`, `completed_at`, `duration`, `interruption_notes`). Do NOT store primary consultation lifecycle timestamps on `queue_entries`. `queue_events` remains the append-only audit/event source.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-032 — Authentication implementation
**Decision:** JWT bearer authentication, bcrypt password hashing, and FastAPI server-side role authorization (Roles: Patient, Staff, Admin). DO NOT build a Doctor Dashboard; OPD staff operates the Reception Control Center.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-033 — Temporary leave policy (staff-managed re-queueing)
**Decision:** Explicit staff-managed re-queueing. When a patient leaves, mark TEMPORARILY_LEFT (excluded from active call sequence). When they return, mark RETURNED. Staff decides/re-queues into WAITING. No automatic position retention or end-of-queue placement.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-034 — Notification abstraction & provider
**Decision:** Implement notification abstraction interface with local/mock provider first for development. Structure it so Twilio can be plugged in without changing queue logic. SMS is primary for MVP. WhatsApp is POST-MVP.
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-035 — Attendant / Family viewer scope
**Decision:** Attendant / Family shared tracking view is POST-MVP.
**Status:** POST-MVP

## Update rule
When a decision changes, mark the old decision SUPERSEDED, add the new decision, update affected docs, append the changelog, and update current project state. Never silently overwrite history.


---

# Documentation Consistency Check

## Decisions recovered
- Q-FLOW is a dynamic, uncertainty-aware OPD queue forecasting + arrival optimization system.
- Multiple doctors and concurrent queues are mandatory.
- OPD Staff / Reception Control Center replaces Doctor Dashboard.
- Patient journey: Get Token / Join Queue → Predict → Travel → Leave → Update → Arrive.
- SMS is required; WhatsApp and Web/PWA are planned/required interfaces.
- Emergency, doctor delay/break, no-show, temporary leave/return and long-consultation/outlier behavior must be modeled.
- Outliers are classified rather than blindly deleted.
- Consultation ETA should be a window, not false precision.
- Google Routes is a travel module, not the innovation.
- Event history and WebSockets are core architecture decisions.
- No fabricated performance claims.

## Conflicts/changes detected
- Earlier doctor-oriented queue-control concepts were superseded by the Reception Control Center.
- Google Maps moved from being a central idea to one module in a broader arrival optimizer.
- Exact ETA examples/percentages were illustrative and are not requirements.
- A previous 10–20-case cold-start example is not a finalized threshold.

## Final Decisions Frozen for MVP
- Database: PostgreSQL with SQLAlchemy ORM, Alembic migrations, and JSONB.
- Consultation storage: Dedicated normalized `consultations` table.
- Auth: JWT bearer + bcrypt + FastAPI server-side roles (Patient, Staff, Admin).
- Temporary leave: Staff-managed re-queueing (`WAITING -> TEMPORARILY_LEFT -> RETURNED -> STAFF_REQUEUES -> WAITING`).
- Notifications: Notification abstraction with local/mock provider first, Twilio pluggable. SMS primary for MVP.
- ETA notification threshold: >= 10 minutes (configurable).
- Prediction progression: Phase 1 rolling median baseline, Phase 2 scikit-learn tabular model. Queue engine decoupled from ML.
- Operator interface: Reception Control Center operates multiple doctor queues; no Doctor Dashboard.
- Post-MVP designations: WhatsApp, Queue Shock Detector, What-If Simulation, Advanced Queue Health Analytics, Attendant/Family shared view.

## Assumptions that must NOT become requirements
- Any accuracy/MAE percentage or minute value for Q-FLOW.
- A universal sample threshold for enabling ML.
- A fixed ETA notification threshold.
- A specific cloud/SMS/WhatsApp provider.
- A confidence percentage before calibration is implemented.
- A claim that Q-FLOW is globally unique or that nobody has implemented a component before.


---

# Q-FLOW Implementation Readiness Check

| Area | Status | Notes |
|---|---|---|
| Product requirements | READY FOR IMPLEMENTATION | Core MVP scope frozen |
| Architecture | READY FOR IMPLEMENTATION | Decoupled queue engine & prediction layer |
| Database | FROZEN & READY | PostgreSQL + SQLAlchemy + Alembic (JSONB) + dedicated `consultations` |
| APIs | READY FOR IMPLEMENTATION | FastAPI contract covering auth, queue, prediction, travel |
| Prediction engine | FROZEN & READY | Phase 1 median baseline $\rightarrow$ Phase 2 scikit-learn (queue engine decoupled) |
| UI/UX | READY FOR IMPLEMENTATION | Reception Control Center + Patient PWA (no Doctor Dashboard) |
| Notifications | FROZEN & READY | Provider abstraction + local/mock provider first; $\Delta \ge 10$ min threshold |
| Security | FROZEN & READY | JWT bearer + bcrypt + FastAPI server roles (Patient/Staff/Admin) |
| Testing | READY FOR IMPLEMENTATION | Primary MVP acceptance test: End-to-end emergency flow |
| AI coding rules | READY | Active |
| Change tracking | READY | Active |

## Status of MVP Decisions: FROZEN
All 10 fundamental architecture, database, queue policy, and prediction decisions have been resolved and frozen for the hackathon MVP.

## Implementation Checklist
- [ ] **1. Project Scaffolding & Database Setup**
  - Initialize FastAPI backend directory structure.
  - Setup SQLAlchemy engine & session for PostgreSQL.
  - Setup Alembic and create initial migration (`hospitals`, `departments`, `users`, `doctors`, `opd_sessions`, `queues`, `queue_entries`, `consultations`, `queue_events`, `notifications`).
- [ ] **2. Authentication & Authorization**
  - Implement password hashing with `bcrypt`.
  - Implement JWT issuance and token validation.
  - Implement FastAPI role dependencies (`Patient`, `Staff`, `Admin`).
- [ ] **3. Queue Engine & Event Store**
  - Implement state machine transitions in backend service.
  - Implement append-only event logging into `queue_events`.
  - Implement staff actions: next, start consultation, complete consultation (updating `consultations`), priority/emergency insertion, pause/resume, doctor delay/break, no-show.
  - Implement temporary leave (`TEMPORARILY_LEFT`) and staff-managed re-queueing (`RETURNED -> STAFF_REQUEUES -> WAITING`).
- [ ] **4. Real-Time Layer (WebSockets)**
  - Implement WebSocket room manager for `/ws/queues/{queue_id}`.
  - Broadcast `QUEUE_UPDATED` and `PREDICTION_UPDATED` events on queue mutations.
- [ ] **5. Prediction Engine (Phase 1: Baseline)**
  - Implement downstream queue traversal and service-time accumulation.
  - Implement rolling/historical median baseline.
  - Implement uncertainty window calculation ($[\text{ETA}_{\text{start}}, \text{ETA}_{\text{end}}]$).
  - Implement reason-code tagger (`PRIORITY_INSERTED`, `DOCTOR_DELAY`, etc.).
  - Ensure queue engine functions seamlessly if ML is absent.
- [ ] **6. Arrival Optimizer & Travel Module**
  - Implement Google Maps Routes API integration module.
  - Compute recommended departure window and safe arrival window.
- [ ] **7. Notification Abstraction & Mock Provider**
  - Implement `NotificationProvider` interface.
  - Implement `MockNotificationProvider` for development logging.
  - Implement configurable $\ge 10$ minutes threshold filter.
- [ ] **8. Frontend: Reception Control Center**
  - Implement multi-doctor/concurrent queue overview.
  - Implement next patient, consultation start/complete, emergency insertion, break/delay controls.
  - Connect WebSocket for live updates.
- [ ] **9. Frontend: Patient PWA**
  - Implement hospital/department/doctor selection & queue join.
  - Implement live queue tracking screen with uncertainty window.
  - Implement "Why did my ETA change?" explanation card.
  - Implement temporary leave request & physical arrival check-in.
  - Connect WebSocket for live updates.
- [ ] **10. Prediction Engine (Phase 2: Tabular ML)**
  - Extract training data from completed `consultations` and `queue_events`.
  - Implement basic scikit-learn duration model with fallback to median baseline.
- [ ] **11. Primary MVP End-to-End Acceptance Demonstration**
  - Run full test: Patient joins $\rightarrow$ Receives token $\rightarrow$ Staff inserts emergency $\rightarrow$ Event recorded $\rightarrow$ Downstream ETAs reforecast $\rightarrow$ WebSocket pushes updates $\rightarrow$ Patient UI displays reason $\rightarrow$ $\ge 10$ min shift triggers mock notification.
