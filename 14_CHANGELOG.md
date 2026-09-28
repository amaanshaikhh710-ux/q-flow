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

## Phase 3 — Core Queue Engine, State Machine & Event Store
### ADDED
- Server-authoritative `QueueEngineService` managing atomic token generation (`Q001`), deterministic position calculation, and authorative queue snapshots.
- `QueueStateMachineService` managing the complete lifecycle: `CREATED -> WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED`, plus `TEMPORARILY_LEFT`, `RETURNED`, `STAFF_REQUEUES`, and `NO_SHOW`.
- Concurrency control using PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) on queues during join.
- Normalized clinical tracking in `consultations` table on consultation start and completion (DEC-031).
- Staff-managed requeueing workflow for temporary leaves (DEC-033).
- Operational disruptions support: doctor delays, doctor breaks (start/end), queue pause and resume.
- Append-only event store audit logging in `queue_events` for every queue mutation.
- Downstream affected patient identification (`get_affected_downstream_entries`).
- Full REST endpoints under `/api/v1/queues` and `/api/v1/queue-entries`.

### TESTING
- 25 comprehensive Phase 3 unit and API tests in `test_queue_engine.py`, `test_queue_state_machine.py`, and `test_queue_api.py`. Total test suite passing: 59/59 tests.

## Phase 3.1 — Queue Hardening
### CHANGED
- Temporary leave (`/leave`) and return (`/return`) endpoints updated to require Staff or Admin role (patients forbidden from directly mutating their own queue state).
- Event naming aligned: normal priority shifts log `PRIORITY_CHANGED`; emergency insertions log `EMERGENCY_INSERTED`.
- Explicit transaction rollback added in API route exception handlers for PostgreSQL integrity.

### TESTING
- Added `test_patient_cannot_leave_or_return_directly` and verified 62/62 tests passing.

## Phase 4 — Prediction + Uncertainty + Dynamic Reforecast Engine
### ADDED
- Alembic migration `74bc8c0b08ae` creating `prediction_snapshots` table with 7 composite indexes for fast entry/queue queries.
- `PredictionSnapshot` model recording predicted consultation windows (`predicted_start_at`, `predicted_end_at`), duration, uncertainty margin, patients ahead, trigger event, model version, and human-readable explanation.
- `BaseDurationPredictor` interface with `RobustMedianPredictor` implementing rolling median and Median Absolute Deviation (MAD) uncertainty bounds, and `SklearnDurationPredictor` with automatic degradation.
- `PredictionFeatureBuilder` implementing 5-tier fallback hierarchy: Doctor+Dept Recent $\rightarrow$ Doctor Historical $\rightarrow$ Dept Historical $\rightarrow$ Global Clinic Historical $\rightarrow$ Safe Default (15.0m).
- Outlier filtering: durations <= 0s (data errors) and > 7200s (operational anomalies) excluded from model training.
- Cumulative wait time calculation accounting for active in-progress consultation elapsed time (`max(60, predicted - elapsed)`), called patient, waiting patients ahead in authoritative priority order, and doctor delays/breaks.
- `ReforecastService` with event-driven dynamic reforecasting on 10 queue disruption event types, idempotency checks on `trigger_event_id`, and >= 10 minute meaningful change threshold detection.
- Context-aware human-readable explanations ("Emergency patient inserted ahead", "Token skipped due to no-show", "Doctor delayed by N min", etc.).
- REST API endpoints:
  - `GET /api/v1/queue-entries/{entry_id}/prediction` (Patient own / Staff / Admin)
  - `GET /api/v1/queue-entries/{entry_id}/prediction/history` (Patient own / Staff / Admin)
  - `GET /api/v1/queues/{queue_id}/predictions` (Staff / Admin)
  - `POST /api/v1/queues/{queue_id}/reforecast` (Staff / Admin)
- Hooked advisory initial prediction snapshot generation into patient `POST /join` queue flow without blocking on failures.

### TESTING
- 20 Phase 4 tests in `test_prediction_baseline.py`, `test_prediction_calculation.py`, `test_reforecast_engine.py`, and `test_prediction_api.py`.
- Full regression suite passing: 82/82 tests passing, 0 failures, 0 regressions.

## Phase 4.1 — Prediction Window Semantics Hardening
### ADDED
- Established and enforced precise semantic definitions for uncertainty-aware consultation windows:
  - `predicted_start_at`: Earliest/central expected consultation start according to deterministic queue state. Patient-facing invariant: NOT a guaranteed exact appointment time.
  - `predicted_end_at`: Expected completion boundary including the uncertainty margin (`predicted_start_at + duration + margin`). Strictly chronologically ordered (`predicted_end_at > predicted_start_at`).
  - `uncertainty_margin_seconds`: Non-negative uncertainty buffer in seconds (`>= 180s`, default `300s`), derived from historical MAD.
  - `predicted_duration_seconds`: Strictly positive estimated duration in seconds (`>= 60s`, default `900s`).
  - `patients_ahead_count`: Non-negative count of active unserviced patients ahead in queue.
  - `explanation`: Patient-facing context explanation for estimate or dynamic reforecast.
  - `model_version`: Model identifier string (`baseline-v1`).
- Pydantic schema validation: Added `ge=0` constraints on all duration, margin, and patient count fields in `PredictionResponse`.
- Adopted patient-facing terminology: "Estimated consultation window".
- Zero fake confidence percentage invariant enforced across models, APIs, and schemas.

### TESTING
- Added `tests/test_prediction_semantics.py` (6 tests) verifying chronological validity, strict ordering (`end > start`), non-negativity guarantees, fallback window semantics, reforecasting preservation, and complete API exposure.
- Full regression suite passing: 88/88 tests passing, 0 failures, 0 regressions.

## Phase 5 — Travel-Aware Arrival Optimization
### ADDED
- Alembic migration `a4a2a2f84047` creating `arrival_plans` table and transient travel origin fields on `queue_entries` (`origin_latitude`, `origin_longitude`, `travel_mode`, `travel_origin_updated_at`).
- `BaseTravelProvider` interface and `TravelEstimateResult` dataclass.
- `MockTravelProvider`: deterministic, configurable transit provider for CI and testing.
- `GoogleRoutesProvider`: Google Routes API v2 integration with traffic-aware duration and variance estimation.
- Automatic provider resolver: falls back to `MockTravelProvider` if Google API key is absent.
- `TravelCache`: in-memory thread-safe 5-minute time-bucketed cache with 10-minute TTL to protect against external API rate limits and costs.
- `ArrivalOptimizationService`: calculates recommended arrival window (`[T_start - 15m, T_start - 5m]`) and departure window (`[T_arr_start - (D+U), T_arr_end - (D+U)]`).
- Dynamic reforecast integration: automatically recalculates departure recommendations when queue disruptions shift consultation windows.
- 10-minute meaningful change detection (`consultation_changed`, `travel_changed`, `is_meaningful_change`).
- Location privacy invariants: origin coordinates are transient, excluded from queue snapshots, events, explanations, and logs.
- REST API endpoints:
  - `POST /api/v1/queue-entries/{entry_id}/travel-origin`
  - `GET /api/v1/queue-entries/{entry_id}/travel`
  - `GET /api/v1/queue-entries/{entry_id}/arrival-plan`
  - `GET /api/v1/queue-entries/{entry_id}/arrival-plan/history`
- Dedicated architecture documentation: `09_ARRIVAL_OPTIMIZATION.md`.

### TESTING
- 15 new unit and integration tests across `test_travel_provider.py`, `test_arrival_optimizer.py`, and `test_travel_api.py`.
- Full regression suite passing: 103/103 tests passing, 0 failures, 0 regressions.

## Phase 5.1 — Travel Provider & Failure Handling Hardening
### CHANGED
- Canonical Google API Key: Standardized on `GOOGLE_ROUTES_API_KEY` as the primary configuration in code, settings, and `.env.example`. Maintained `GOOGLE_MAPS_API_KEY` strictly as a legacy alias.
- Transparent Travel Statuses: Established explicit three-status semantics: `OPTIMIZED`, `DEGRADED`, and `UNAVAILABLE`.
- Failure Handling Hardening: Configured Google Routes API failures (timeouts, 4xx, 5xx, malformed responses, quota exhaustion) never silently substitute a fake traffic-aware estimate or claim `google_routes` / `OPTIMIZED`. Instead, they cleanly return `travel_status = "DEGRADED"` with `travel_provider = "mock"` and clear patient explanation ("Travel estimate temporarily unavailable. Your consultation estimate is still available.").
- Development/Local Clarification: When `MockTravelProvider` is used in development without an API key, arrival plans clearly state "Development travel estimate."
- API Key Security: Added test verifying Google API keys are never exposed in responses or serializations.

### TESTING
- Added `tests/test_travel_hardening.py` (8 new tests) verifying Google success, local mock provider, configured API failure degradation, timeout resilience, 500 error handling, malformed response handling, missing/placeholder key behavior, and zero API key exposure.
- Full regression suite passing: 111/111 tests passing, 0 failures, 0 regressions.

## Phase 6 — Real-Time WebSocket Updates & Notification Intent/Dispatcher
### ADDED
- Alembic migration `347d1479409f` adding `trigger_event_id`, `title`, `message`, `payload_json`, `failure_reason`, and unique idempotency constraint `uq_notifications_entry_trigger_type` on `(queue_entry_id, trigger_event_id, notification_type)` to the `notifications` table.
- WebSocket subsystem (`app/websocket/`):
  - `schemas.py`: Typed schemas for WebSocket messages, snapshots, prediction summaries, and arrival summaries.
  - `manager.py`: Thread-safe async `ConnectionManager` with reconnect snapshot support, patient/queue connection tracking, and stale socket cleanup.
  - `auth.py`: WebSocket JWT authentication supporting both `?token=` query parameters and `Authorization: Bearer` headers, enforcing strict patient isolation.
  - `snapshot_service.py`: `WebSocketSnapshotService` assembling patient-safe snapshots without PII or coordinates.
  - `handlers.py`: `WS /api/v1/ws/patient/{entry_id}` and `WS /api/v1/ws/queue/{queue_id}` endpoints.
- Notification intent and dispatcher subsystem (`app/services/notifications/`):
  - `base.py`: `BaseNotificationProvider` interface.
  - `mock_provider.py`: In-memory `MockNotificationProvider` for CI testing and local execution with failure simulation.
  - `service.py`: `NotificationService` enforcing $\ge 10$-minute threshold, deterministic idempotency, and non-blocking failure handling.
- Real-time dispatcher (`app/services/realtime_dispatcher.py`):
  - Bridges dynamic reforecasting to WebSocket connections and notifications.
  - Dispatches updates **strictly after** database transactions commit.
  - Targets patient-specific updates only to affected downstream patients.
- Dedicated documentation: `10_REALTIME_AND_NOTIFICATIONS.md`.

### TESTING
- Added `tests/test_notifications.py` (6 tests).
- Added `tests/test_websocket.py` (9 tests).
- Added `tests/test_phase6_integration.py` (2 tests).
- Full regression suite passing: 128/128 tests passing, 0 failures, 0 regressions.

## Major Usability & Architecture Improvement Pass
### ADDED
- Unified Appointment & Queue System:
  - Staff walk-in and phone patient bookings (`POST /api/v1/queues/{queue_id}/staff-book`) and patient online bookings (`POST /api/v1/queues/{queue_id}/join`) now use the EXACT SAME backend queue table (`queue_entries`), the SAME atomic `token_number` sequence generator, and the SAME queue prediction/state engine.
  - Added `booking_source` (`ONLINE`, `STAFF`, `WALK_IN`, `PHONE`) and `notes` fields to `QueueEntry` model and responses.
  - Concurrency-safe token numbering: Implemented atomic token calculation with `with_for_update()` (PostgreSQL) and an optimistic retry loop on unique constraint collisions (`uq_queue_token_number`) for cross-database safety (PostgreSQL + SQLite).
- Hospital-Scoped Staff Authorization:
  - Added `hospital_id` foreign key on `User` entity, binding staff users strictly to their assigned hospital.
  - Added `get_queue_hospital_id` and `verify_staff_hospital_access` dependency helpers. All staff mutation endpoints (queue actions, staff bookings, patient status updates) reject cross-hospital actions with HTTP 403 Forbidden. Admins retain cross-hospital superuser privileges.
  - Added `GET /api/v1/discovery/staff-hospital` returning only the staff member's assigned hospital, departments, and active queues.
- Patient UX & Dashboard Redesign:
  - Added `GET /api/v1/queue-entries/my` returning strictly the logged-in patient's appointments categorized into `today`, `upcoming`, and `past` with rich hierarchy (hospital, department, doctor, queue, prediction, arrival plan, travel status).
  - Created dedicated `PatientDashboardPage.tsx` with clean tabular views, status badges, wait times, token numbers, leave-by times, and `[Open in Google Maps]` links.
  - Created simplified 4-step booking flow in `SimpleBookingPage.tsx` (Hospital -> Department -> Doctor/Queue -> Review & Confirm).
  - Added staff walk-in/phone booking modal (`StaffBookModal.tsx`) within `StaffLandingPage.tsx`.
- Google Maps Integration:
  - Enhanced travel endpoint to calculate both driving and walking travel options.
  - Added external `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&travelmode=...` navigation links for patients.
  - Failure handling: When API keys are missing or route lookups fail, the system returns `UNAVAILABLE` or `DEGRADED` status without crashing, falling back honestly without fabricating travel times.
- Development & Testing Assets:
  - Created exactly 5 demo staff accounts across 2 hospitals, fully documented in `/docs/STAFF_TEST_ACCOUNTS.md`.
  - Added comprehensive automated test suite `tests/test_appointment_sync.py` covering staff booking followed by patient booking, patient booking followed by staff booking, 8-thread concurrent bookings, multi-doctor/queue isolation, multi-hospital isolation, cross-hospital access denial, patient appointment isolation, and Google Maps failure handling.

### CHANGED
- Public registration (`POST /api/v1/auth/register`) strictly coerces role to `patient`; staff registration is disabled from public access.
- Normalized timezone handling across SQLite and PostgreSQL to prevent naive/aware datetime subtraction errors in reforecasting and arrival optimization.
- Updated `16_DECISIONS.md` with `DEC-036` (Unified Queue Sequence & Transaction-Safe Numbering) and `DEC-037` (Hospital-Scoped Staff Authorization).
- Updated database schema (`05_DATABASE_SCHEMA.md`) and API specifications (`06_API_SPECIFICATION.md`).

### REMOVED
- Public staff registration capability.
- Doctor dashboard references (receptionist/staff control center is the authoritative staff UI).

## Strict Correction, Real-World Workflow & UI Overhaul Pass
### FIXED
- Removed duplicate seed hospitals: Replaced duplicated dummy institutions with 5 distinct, realistic Mumbai municipal/government hospital entities (KEM Hospital Parel, BYL Nair Hospital Mumbai Central, Lokmanya Tilak Sion Hospital, Sir J.J. Hospital Byculla, Rajawadi Hospital Ghatkopar).
- Removed duplicate doctors: Assigned distinct named specialists to each hospital and department.
- Fixed staff portal routing and navigation: Removed "Public View OPD" and public hospital browsing links from the staff experience. Staff can now only view and operate their assigned hospital.
- Fixed queue state lifecycle: Introduced explicit `BOOKED` and `ARRIVED` states to accurately represent real-world OPD progression (`BOOKED -> ARRIVED -> WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED`).
- Fixed consultation duration tracking: Automatically records `started_at`, `completed_at`, and calculates exact `duration_seconds` from real timestamps.

### ADDED
- 5 Distinct Development Staff Accounts:
  - Created 5 unique staff accounts assigned across the 5 distinct Mumbai public hospitals (`staff.kem@qflow.com`, `staff.nair@qflow.com`, `staff.sion@qflow.com`, `staff.jj@qflow.com`, `staff.rajawadi@qflow.com`, password: `password123`).
  - Documented full credentials in `/docs/STAFF_TEST_ACCOUNTS.md` and `STAFF_TEST_ACCOUNTS.md`.
- Patient Arrival Control System:
  - Added `POST /api/v1/queue-entries/{entry_id}/arrive` endpoint allowing staff to mark physical patient arrival at the OPD.
  - Added `POST /api/v1/queue-entries/{entry_id}/wait` endpoint to advance arrived patients into the active waiting queue.
  - Added `arrived_at` timestamp to `QueueEntry` model and responses.
  - Added `total_booked` and `booked_entries` to authoritative `QueueSnapshotResponse`.
- Real Notification Provider Integration:
  - Implemented `TwilioNotificationProvider` in `app/services/notifications/twilio_provider.py` using `httpx` to send real SMS alerts via Twilio REST API.
  - Added `send_queue_event_notification` to dispatch queue updates (delays, emergencies, arrival confirmations) to patients.
  - Transparently indicates `CONFIGURATION REQUIRED` when external credentials are not set without faking delivery.
- Comprehensive Test Suite:
  - Created `tests/test_correction_suite.py` covering all 18 mandatory real-world scenarios: unified sequence, race conditions, doctor scopes, hospital queue isolation, cross-hospital access denial, cross-patient access denial, arrival state transitions, consultation timestamps and duration calculation, queue advancement, prediction updates on long consultations, doctor delays, emergency insertions, notification dispatch, driving and walking travel calculations, and honest Google Maps failure handling.

### REMOVED
- "Public View OPD" / "Public Directory" navigation link and patient-style hospital browsing within the staff portal.
- Unused duplicate hospital and doctor seed templates.

### CHANGED
- Updated `QueueStateMachineService` state transitions to enforce `BOOKED -> ARRIVED -> WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED`.
- Updated `QueueEngineService.join_queue`: Online bookings start in `BOOKED` state awaiting patient physical arrival.
- Updated `QueueEngineService.staff_book_appointment`: Walk-in bookings are automatically marked `WAITING` with `arrived_at = now`; phone bookings are marked `BOOKED`.
- Updated `QueueControlPage.tsx` staff UI:
  - Added "Booked (Pre-Arrival)" metric card.
  - Added "Booked Patients (Awaiting Physical Arrival)" table with one-click "Mark Arrived" action.
  - Added "ARRIVED" and "BOOKED" status indicators in the active queue table.

### DATABASE
- Schema updated:
  - `QueueEntry`: Added `arrived_at` nullable datetime column; added `BOOKED` and `ARRIVED` enum values to `QueueEntryStatus`.
  - `QueueEvent`: Added `PATIENT_ARRIVED` and `APPOINTMENT_BOOKED` to `QueueEventType`.
  - Migration script `add_arrived_at_to_queue_entries.py` applied to local database.

### API
- `POST /api/v1/queue-entries/{entry_id}/arrive`: Marks physical patient arrival (hospital-scoped authorization).
- `POST /api/v1/queue-entries/{entry_id}/wait`: Moves arrived patient into active waiting line.
- `GET /api/v1/queues/{queue_id}/snapshot`: Now returns `total_booked` and `booked_entries` alongside waiting and active counts.

### UI/UX
- Staff Landing Page: Strictly hospital-scoped. Shows hospital operational summary, doctors, and queues.
- Queue Control Page: Displays pre-arrival booked patients, arrived patients, waiting line, active consultation, and operational disruptions (delay, emergency).
- Patient Dashboard: Simple, mobile-first design displaying "MY APPOINTMENTS" categorized into Today, Upcoming, and Past with consultation window, token number, driving/walking travel times, and recommended departure time.

### SECURITY
- Hospital Data Isolation: Server-side authorization blocks staff from accessing or modifying queues, appointments, doctors, or analytics outside their assigned hospital (HTTP 403 Forbidden).
- Patient Data Isolation: Server-side authorization blocks patients from accessing other patients' appointments (HTTP 403 Forbidden).
- Public Staff Registration: Completely blocked; public sign-up is strictly coerced to role `patient`.

### NOTIFICATIONS
- Twilio SMS Provider implemented for real SMS dispatch.
- Fallback to mock provider in local/dev with honest logging (no fake carrier delivery claims).
- Configurable threshold for ETA shifts and operational queue event alerts.

### TESTING
- Automated test suite `backend/tests/test_correction_suite.py` executed: 16/16 test functions PASSED covering all 18 mandatory requirements.

### DOCUMENTATION
- Updated `STAFF_TEST_ACCOUNTS.md`, `14_CHANGELOG.md`, `15_CURRENT_PROJECT_STATE.md`, `05_DATABASE_SCHEMA.md`, `08_QUEUE_STATE_MACHINE.md`, `06_API_SPECIFICATION.md`.

## Phase 7.2 — Historical Data Reporting, CSV Export & OTP Self-Registration
### ADDED
- Historical Hospital Appointments Query & Export:
  - Added `GET /api/v1/hospital/historical-appointments` with server-side filtering by date preset (`today`, `yesterday`, `this_week`, `last_week`, `this_month`), custom date range (`start_date`, `end_date`), doctor, department, queue, appointment status, and booking source (`ONLINE`, `PHONE`, `WALK_IN`, `STAFF`).
  - Added `GET /api/v1/hospital/historical-appointments/export` generating filtered CSV file stream for hospital records.
  - Server-side hospital isolation: Staff can only query and export historical records for their assigned hospital (`403 Forbidden` on cross-hospital access).
  - Server-side pagination with `skip` and `limit`.
- Patient OTP Self-Registration & Authentication:
  - Added `POST /api/v1/auth/otp/request`: Generates 6-digit numeric OTP code with 10-minute expiry for phone or email. Dispatches via SMS/Email provider or logs for development with honest provider status reporting (`CONFIGURATION REQUIRED` if external provider credentials missing).
  - Added `POST /api/v1/auth/otp/verify`: Validates OTP code, marks token verified, logs in existing user or automatically self-registers a new patient with role `patient`.
  - Added `OTPToken` model and `otp_tokens` table in SQLite/PostgreSQL.
- Frontend Historical Reports & Analytics:
  - Added `StaffHistoricalReportsPage.tsx` with preset filters, custom date pickers, multi-column data table, summary statistics (total, completed, no-show, avg consultation time, avg wait time), and one-click CSV export.
  - Added navigation link in Staff portal header and landing page.

### TESTING
- `backend/tests/test_otp_auth.py`: 5/5 PASSED (request/verify registration, existing user login, invalid OTP rejected, expired OTP rejected, public registration coercion to patient).
- `backend/tests/test_historical_reporting.py`: 2/2 PASSED (filter presets, custom date range, doctor/department/status filters, CSV export, cross-hospital isolation).

## Phase 8 — Final End-to-End Correction, Hospital Isolation & Database Purge
### ADDED
- Comprehensive 28-point automated verification suite in `backend/tests/verify_all_requirements.py` testing patient registration, staff isolation, cross-hospital denial, state transitions, GPS coordinate handling, CSV export, and configuration handling.
- `backend/scripts/clean_and_seed.py` standalone database purification script utilizing PostgreSQL `TRUNCATE TABLE ... CASCADE` to cleanly wipe obsolete duplicate entities and seed 5 reference hospitals, 15 distinct doctors, 15 queues, and 5 staff accounts.
- Portable Node.js v20.18.0 environment in `.node/node-v20.18.0-win-x64` enabling local Vite production compilation without requiring global host Node installations.
- 1-click hospital staff login switchboard in `LoginPage.tsx` allowing instant, zero-credential switching between KEM, BYL Nair, Sion, Sir J.J., and Rajawadi staff sessions.

### CHANGED
- Rebuilt frontend production bundle (`frontend/dist/`) via `vite build` to resolve stale UI artifacts served by Python `serve_spa.py`.
- Corrected `StaffHistoricalReportsPage.tsx` TypeScript types and imports to adhere to strict `verbatimModuleSyntax`.
- Updated `GET /api/v1/discovery/staff-hospital` to strictly derive hospital scope from `current_user.hospital_id`, removing all client-supplied `hospital_id` query parameters.
- Replaced single static staff login button in `LoginPage.tsx` with five distinct hospital login options.

### REMOVED
- Completely removed 425 duplicate "Apex Multispeciality Hospital" entries and 465 duplicate queues from the PostgreSQL database.
- Removed all "Public OPD Directory", "Choose Hospital", and "Switch Hospital" navigation elements from the Hospital Staff Portal.
- Removed all duplicate doctor entries ("Dr. Rajesh Kumar" repeated across hospitals).

### FIXED
- Fixed cross-hospital authorization denial bug: KEM staff managing valid KEM queues previously received unexpected hospital boundary errors due to decoupled session models.
- Fixed `StatusBadges.tsx` missing `BOOKED` and `ARRIVED` state badge configurations.
- Fixed `SimpleBookingPage.tsx` and `PatientDashboardPage.tsx` unused imports and build warnings.
- Fixed GPS coordinate input handler in travel endpoints to accept `DRIVE` travel mode.

### DATABASE
- Exactly 5 distinct reference hospitals:
  1. King Edward Memorial (KEM) Hospital, Parel (19.0024, 72.8428)
  2. BYL Nair Charitable Hospital, Mumbai Central (18.9723, 72.8188)
  3. Lokmanya Tilak Municipal General Hospital, Sion (19.0371, 72.8601)
  4. Sir J.J. Group of Hospitals, Byculla (18.9633, 72.8339)
  5. Rajawadi Municipal General Hospital, Ghatkopar (19.0784, 72.9069)
- Exactly 15 distinct departments (3 per hospital) and 15 distinct doctors (no repeated doctor names).
- Exactly 15 active OPD queues (1 per doctor/department).
- Exactly 5 staff user accounts tied strictly to their respective hospitals.
- Primary demo patient: Aarav Sharma (`patient@qflow.com`).

### API
- `GET /api/v1/discovery/staff-hospital`: Strictly hospital-scoped.
- `GET /api/v1/hospital/historical-appointments`: Strictly filtered by staff's `hospital_id`.
- `GET /api/v1/hospital/historical-appointments/export`: Strictly filtered CSV export for staff's hospital.
- `POST /api/v1/queues/{queue_id}/staff-book`: Books walk-in or phone patient directly into active OPD queue with unified token sequence.

### UI/UX
- Staff portal header displays only the logged-in staff's hospital name and operational center title.
- Patient portal displays clean, non-duplicated hospital cards with distinct addresses and coordinates.
- Patient booking flow dynamically filters: Hospital -> Hospital Departments -> Hospital Doctors -> Doctor Queues.

### SECURITY
- Strict multi-hospital isolation: Staff token encodes `hospital_id`; all backend queue, appointment, and historical endpoints verify `staff.hospital_id == queue.hospital_id`. Cross-hospital attempts receive `403 Forbidden`.
- Patient data isolation: Patient tokens cannot query or mutate queue entries belonging to other patients (`403 Forbidden`).

### NOTIFICATIONS
- Honest reporting: Outbound notifications fall back to local development logging when Twilio credentials are unconfigured. Marked as `CONFIGURATION REQUIRED`.

### TESTING
- `backend/tests/verify_all_requirements.py`: 28 tests evaluated, 26 PASSED, 2 CONFIGURATION REQUIRED, 0 FAILED.


