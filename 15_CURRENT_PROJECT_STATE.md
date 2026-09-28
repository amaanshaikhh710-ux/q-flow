# Q-FLOW — Current Project State

## Overall Status: COMPLETE (MVP REAL-WORLD HARDENED)

The Q-FLOW platform has undergone a comprehensive strict correction and overhaul pass. All architectural boundaries between Patient Portal, Hospital Staff Portal, and Admin/Backend Provisioning are strictly separated and enforced.

### Status Indicators Summary:
- **COMPLETE**: Core queue engine, hospital-scoped staff authorization, 5 distinct staff test accounts, patient arrival control, real consultation duration tracking, unified appointment numbering, patient portal, staff dashboard, queue event audit trail, Google Maps driving/walking estimation, and 18 mandatory test scenarios.
- **CONFIGURATION REQUIRED**: Live Twilio SMS credentials, Google Maps/Routes API key, and Production SMS OTP provider.
- **NOT IMPLEMENTED / POST-MVP**: WhatsApp Business API, Queue Shock Detector, Dynamic multi-doctor load balancing.

---

## 1. Patient Portal — COMPLETE
- **Self-Registration & Login**: Patients register with mobile/email and login.
- **Hospital & Doctor Discovery**: Patients browse registered public hospitals, select department/OPD, select doctor, and view active sessions.
- **Booking Flow**: Simple 4-step booking creating a unified `QueueEntry` with atomic token numbering (`BOOKED` status).
- **Patient Dashboard**: Displays "MY APPOINTMENTS" categorized into Today, Upcoming, and Past. Shows token number, estimated consultation window, driving and walking travel times, recommended departure time, and Google Maps direct navigation.
- **Patient Data Isolation**: Patients can only see and access their own appointments (server-enforced HTTP 403).

## 2. Hospital Staff Portal — COMPLETE
- **Zero Public Staff Registration**: Public sign-up is strictly locked to role `patient`. Staff accounts are provisioned solely by admin/backend seed scripts.
- **5 Distinct Staff Test Accounts**: Provisioned across 5 distinct Mumbai municipal hospitals (`staff.kem@qflow.com`, `staff.nair@qflow.com`, `staff.sion@qflow.com`, `staff.jj@qflow.com`, `staff.rajawadi@qflow.com`). Documented in `STAFF_TEST_ACCOUNTS.md`.
- **Strict Hospital Data Isolation**: Backend authorization strictly prevents staff of Hospital A from accessing or mutating data of Hospital B (HTTP 403 Forbidden).
- **Removed "Public View OPD"**: Staff portal contains zero patient-style hospital browsing.
- **Hospital Operations Dashboard**: Real-time counters (doctors, active queues, waiting patients, in-consultation, completed, delays, emergencies) and doctor cards.
- **Staff Phone / Walk-in Booking**: Staff can add appointments directly into the active OPD queue. Walk-ins enter `WAITING` state; phone bookings enter `BOOKED` state. Single source of truth.
- **Patient Arrival Control**: Staff marks physical patient arrival (`POST /api/v1/queue-entries/{entry_id}/arrive` and `/wait`).
- **Consultation Lifecycle Control**: Staff starts consultation (`started_at`), ends consultation (`completed_at`), with automatic calculation of exact duration in seconds.
- **Operational Disruption Controls**: Staff can record doctor delays, declare emergency insertions, and log reasons.
- **Queue Event History**: Append-only event store recording every operational transition with timestamps.

## 3. Queue & Prediction Engine — COMPLETE
- **Single Source of Truth**: Online bookings, phone bookings, and walk-in bookings use the exact same `queue_entries` table, same sequence generator, and same prediction pipeline.
- **Transaction-Safe Token Generation**: Atomic `token_number` generation with `with_for_update` and collision retry loops.
- **State Machine**: `BOOKED -> ARRIVED -> WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED`.
- **Real Operational Data Feeds Predictions**: Predictions use real timestamps (`arrived_at`, `started_at`, `completed_at`, `duration_seconds`) rather than fabricated numbers.
- **Dynamic Reforecasting**: Recalculates waiting times and consultation windows whenever consultations complete, doctor delays occur, emergencies are inserted, or no-shows are marked.

## 4. Travel & Arrival Optimization — COMPLETE (CONFIGURATION REQUIRED FOR LIVE GOOGLE DATA)
- **Google Maps Integration**: Supports both Driving (`DRIVE`) and Walking (`WALK`) modes.
- **Recommended Departure Time**: Combines predicted consultation window, travel transit duration, and arrival buffer to suggest an optimal departure time.
- **Honest Degradation**: When `GOOGLE_ROUTES_API_KEY` is not configured, the system marks travel status as `DEGRADED` with development estimates. Never fabricates fake transit times.

## 5. Notifications — COMPLETE (CONFIGURATION REQUIRED FOR LIVE SMS)
- **Real Provider Implementation**: `TwilioNotificationProvider` implemented via `httpx` to send real carrier SMS alerts.
- **Safe Development Fallback**: `MockNotificationProvider` logs outbound alerts locally without claiming carrier delivery.
- **Queue Update Triggers**: Dispatches alerts for ETA shifts $\ge 10$ minutes, doctor delays, and emergency queue shifts.

## 6. Historical Data Reporting & CSV Export — COMPLETE
- **Historical Queries**: Staff can inspect past days' appointments via `GET /api/v1/hospital/historical-appointments` with date presets (`today`, `yesterday`, `this_week`, `last_week`, `this_month`) or custom date ranges (`start_date`, `end_date`).
- **Comprehensive Filtering**: Server-side filtering by doctor, department, queue, appointment status (`BOOKED`, `ARRIVED`, `WAITING`, `IN_CONSULTATION`, `COMPLETED`, `NO_SHOW`), and booking source (`ONLINE`, `PHONE`, `WALK_IN`, `STAFF`).
- **CSV Data Export**: Streamed download via `GET /api/v1/hospital/historical-appointments/export` with applied filters.
- **Hospital Isolation**: Server-enforced hospital scope ensures staff only access their assigned hospital's historical records.
- **Staff UI**: Dedicated "Historical Reports & Exports" page with KPI summary cards, filter bar, paginated data table, and export button.

## 7. Patient OTP Self-Registration — COMPLETE (CONFIGURATION REQUIRED FOR LIVE SMS)
- **OTP Request**: `POST /api/v1/auth/otp/request` generates 6-digit numeric OTP with 10-minute expiry for phone or email.
- **OTP Verification & Self-Registration**: `POST /api/v1/auth/otp/verify` validates code and automatically registers new users with role `patient`.
- **Zero Public Staff Registration**: Public registration cannot assign the `staff` role; staff accounts must be provisioned via admin/seed scripts.
- **Honest Status**: Reports `CONFIGURATION REQUIRED` if external SMS gateway credentials are not configured; logs OTP locally for development.

## 8. Testing — COMPLETE
- **Comprehensive Verification Suite**: `backend/tests/verify_all_requirements.py`: 28 tests evaluated, **26 PASSED**, **2 CONFIGURATION REQUIRED**, **0 FAILED**.
  - Validates patient registration, patient login, patient isolation, 5-hospital staff login, staff hospital scope, cross-hospital API denial (HTTP 403), hospital data isolation, doctor/hospital relationships, queue/hospital relationships, patient booking, staff booking, sequential token generation (#105 -> #106), 5-state lifecycle transitions (`BOOKED -> ARRIVED -> WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED`), consultation duration tracking, doctor delay event, emergency priority insertion (#107), no-show handling, prediction snapshot engine, historical query filtering, historical hospital isolation, and CSV data export.
- **Correction Suite**: `backend/tests/test_correction_suite.py`: 16/16 tests PASSED.
- **OTP Auth Suite**: `backend/tests/test_otp_auth.py`: 5/5 tests PASSED.
- **Historical Reporting Suite**: `backend/tests/test_historical_reporting.py`: 2/2 tests PASSED.

## 9. Database & Entity State — VERIFIED
- **Hospitals (5 Distinct Municipal Reference Hospitals)**:
  1. King Edward Memorial (KEM) Hospital, Parel (19.0024, 72.8428)
  2. BYL Nair Charitable Hospital, Mumbai Central (18.9723, 72.8188)
  3. Lokmanya Tilak Municipal General Hospital, Sion (19.0371, 72.8601)
  4. Sir J.J. Group of Hospitals, Byculla (18.9633, 72.8339)
  5. Rajawadi Municipal General Hospital, Ghatkopar (19.0784, 72.9069)
- **Departments & Doctors (15 Distinct Doctors, No Duplicates)**:
  - KEM: General Medicine (Dr. Arjun Mehta), Dermatology (Dr. Neha Kulkarni), Cardiology (Dr. Rohan Deshpande)
  - Nair: General Medicine (Dr. Sameer Patil), Dermatology (Dr. Ayesha Khan), Orthopedics (Dr. Vivek Shah)
  - Sion: General Medicine (Dr. Aditya Rao), Pediatrics (Dr. Pooja Menon), Orthopedics (Dr. Siddharth Shah)
  - J.J.: General Medicine (Dr. Ananya Joshi), Cardiology (Dr. Kunal Bhat), Pediatrics (Dr. Meera Nair)
  - Rajawadi: General Medicine (Dr. Nikhil Joshi), Dermatology (Dr. Riya Deshmukh), ENT (Dr. Varun Kulkarni)
- **Queues**: Exactly 15 active OPD queues (1 per doctor).
- **Staff Accounts**: 5 distinct accounts (`staff.kem@qflow.com`, `staff.nair@qflow.com`, `staff.sion@qflow.com`, `staff.jj@qflow.com`, `staff.rajawadi@qflow.com`), all mapped strictly to their single hospital.
- **Demo Patient**: Aarav Sharma (`patient@qflow.com`).



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
