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
