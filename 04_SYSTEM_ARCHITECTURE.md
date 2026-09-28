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
