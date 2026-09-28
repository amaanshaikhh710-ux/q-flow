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

## DEC-036 — Unified Queue Sequence & Transaction-Safe Numbering
**Decision:** Staff-created appointments (walk-in and phone) and patient-created appointments (online) use the EXACT SAME backend queue table (`queue_entries`), the SAME atomic `token_number` sequence generator, and the SAME queue prediction/state engine. No separate numbering scheme or secondary queue is permitted.
To prevent duplicate token numbers under concurrent booking conditions, token allocation is made transaction-safe via `with_for_update()` (PostgreSQL) combined with an optimistic retry loop (up to 5 attempts) on unique constraint collisions (`uq_queue_token_number`) across all database engines (including SQLite).
**Status:** ACCEPTED / FINAL FOR MVP

## DEC-037 — Hospital-Scoped Staff Authorization & Access Boundaries
**Decision:** Staff user accounts are strictly bound to a single hospital via `users.hospital_id`.
All staff mutation and query endpoints (queue actions, staff bookings, patient status updates) enforce server-side validation against `users.hospital_id`. Staff attempting to access or modify queues belonging to another hospital are rejected with HTTP 403 Forbidden. Admins bypass hospital scoping.
Public user registration is strictly restricted to the `patient` role. Staff accounts can only be provisioned through seed scripts or administrative onboarding.
**Status:** ACCEPTED / FINAL FOR MVP

## Update rule
When a decision changes, mark the old decision SUPERSEDED, add the new decision, update affected docs, append the changelog, and update current project state. Never silently overwrite history.
