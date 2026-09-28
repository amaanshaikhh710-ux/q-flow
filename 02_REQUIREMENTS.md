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
