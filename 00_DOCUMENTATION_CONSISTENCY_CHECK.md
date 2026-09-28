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
