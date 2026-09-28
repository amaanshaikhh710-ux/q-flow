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
