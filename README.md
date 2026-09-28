# Q-FLOW — Dynamic, Uncertainty-Aware OPD Queue Forecasting & Arrival Optimization Platform

Q-FLOW is an intelligent healthcare operations and patient journey platform that eliminates crowded hospital waiting rooms. By combining robust statistical estimation with tabular machine learning and real-time operational state tracking, Q-FLOW predicts dynamically shifting outpatient department (OPD) consultation times, continuously reforecasts wait windows, and synchronizes arrival recommendations with live clinic workflows.

---

## 1. Project Overview

In traditional hospital Outpatient Departments (OPD), patients arrive early and wait for hours in congested, infection-prone waiting halls due to consultation time volatility, unscheduled emergencies, and doctor delays.

Q-FLOW transforms this experience into a calm, transparent digital queue:
- **Patients** receive live digital tickets with dynamic consultation windows (e.g. 10:15 AM – 10:30 AM), honest uncertainty intervals (P10–P90), transparent explanations ("Why this estimate?"), and traffic-aware departure planning ("Leave by 9:45 AM").
- **Clinical & Reception Staff** manage queue velocity, record doctor breaks or operational delays, and triage emergency arrivals with automatic downstream ETA recalculation and real-time push updates.

---

## 2. System Architecture

```
                                  +---------------------------------------+
                                  |         PATIENT / STAFF CLIENTS       |
                                  |     (React 19 + TypeScript + Vite)    |
                                  +-------------------+-------------------+
                                                      |
                                          HTTP / REST | WebSocket (Push)
                                                      v
                                  +---------------------------------------+
                                  |         FASTAPI BACKEND CORE          |
                                  |  - RBAC & JWT Authentication          |
                                  |  - Queue State Machine                |
                                  |  - Dynamic Reforecast Engine          |
                                  |  - WebSocket Connection Manager       |
                                  +---------+-------------------+---------+
                                            |                   |
                     +----------------------+                   +----------------------+
                     v                                                                 v
+------------------------------------------+                       +------------------------------------------+
|         PREDICTION SUBSYSTEM             |                       |        INTEGRATIONS & STORAGE            |
|  1. PredictionFeatureExtractor (No PII)  |                       |  - PostgreSQL 16 (Authoritative Store)   |
|  2. HistGradientBoostingRegressor (ML)   |                       |  - Alembic (Schema Versioning)           |
|  3. RobustMedianPredictor (Fallback)     |                       |  - Google Routes API / Degraded Provider |
|  4. Uncertainty Interval Bounds (MAD)    |                       |  - Pluggable Notification System         |
+------------------------------------------+                       +------------------------------------------+
```

---

## 3. Technology Stack

- **Backend**: Python 3.13 / 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn.
- **Machine Learning**: Scikit-Learn (HistGradientBoostingRegressor), Joblib, NumPy.
- **Database**: PostgreSQL 16 with Alembic transactional migrations.
- **Frontend**: React 19, TypeScript, Vite, TanStack Query v5, Tailwind CSS, Lucide Icons.
- **Real-Time Communications**: Native WebSockets with JWT token authentication and heartbeat monitoring.
- **Testing & QA**: Pytest, Playwright (Chromium/Edge browser automation).
- **Deployment**: Multi-stage Docker, Nginx reverse proxy, Docker Compose.

---

## 4. Local Setup & Installation

### Prerequisites
- Python 3.12 or 3.13
- Node.js v20+ and npm v10+
- PostgreSQL 16+ running locally or in Docker

### Step 1: Clone Repository
```bash
git clone https://github.com/your-org/q-flow.git
cd q-flow
```

### Step 2: Backend Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Frontend Setup
```bash
cd ../frontend
npm install
```

---

## 5. Environment Variables Configuration

### Backend Configuration (`backend/.env`)
Copy `backend/.env.example` to `backend/.env`:
```ini
APP_NAME=Q-FLOW
APP_ENV=development
DEBUG=True
API_V1_PREFIX=/api/v1
DOCS_ENABLED=True

# CORS Configuration
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000

# PostgreSQL Connection String
DATABASE_URL=postgresql://postgres:<password>@localhost:5432/qflow

# Security
JWT_SECRET=replace_with_a_secure_random_64_character_hex_secret_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Operational Thresholds
ETA_NOTIFICATION_THRESHOLD_MINUTES=10
DEFAULT_ARRIVAL_BUFFER_MINUTES=10
TRAVEL_CACHE_TTL_SECONDS=600

# External Providers
TRAVEL_PROVIDER=auto
GOOGLE_ROUTES_API_KEY=
NOTIFICATION_PROVIDER=mock
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
```

### Frontend Configuration (`frontend/.env`)
Copy `frontend/.env.example` to `frontend/.env`:
```ini
VITE_API_BASE_URL=http://localhost:8000
```

---

## 6. Database Setup & Migrations

Execute database migrations using Alembic:
```bash
cd backend
python -m alembic upgrade head
```

Verify migration status:
```bash
python -m alembic current
# Expected: 347d1479409f (head)
```

Seed initial demo data:
```bash
python scripts/seed_demo.py
```

---

## 7. Machine Learning Queue Prediction

Q-FLOW features a **Hybrid Intelligent Prediction Engine**:
- **Feature Extraction**: 11 operational signals (`day_of_week`, `hour_of_day`, `minute_of_hour`, `priority_code`, `patients_ahead`, `rolling_recent_duration_median`, `historical_doctor_duration_median`, `historical_dept_duration_median`, `session_elapsed_minutes`, `completed_in_session_count`, `has_emergency_ahead`). Strictly operational; zero patient PII.
- **Primary Model**: `HistGradientBoostingRegressor` with L1 absolute error loss for median estimation.
- **Fail-Safe Fallback**: `RobustMedianPredictor` with IQR outlier rejection. Instantly takes over if the ML model is uninitialized, corrupted, or produces out-of-bounds outputs (<60s or >7200s).
- **Diagnostics API**: `GET /api/v1/predictions/model-status` returns operational model health and validation metrics.

> [!NOTE]
> **Scientific Integrity Notice**:
> ML model validation currently uses synthetic/demo data because real completed consultation history was unavailable in the local database. Production accuracy requires retraining and validation on real completed consultation data.

---

## 8. Running the Backend

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/health/ready`

---

## 9. Running the Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```
- Access application: `http://localhost:5173`

---

## 10. Docker Deployment

Launch PostgreSQL, FastAPI backend, and Nginx-fronted React frontend in orchestrated containers:
```bash
docker-compose up -d --build
```
- Frontend: `http://localhost:5173` (or `http://localhost:80`)
- Backend API: `http://localhost:8000`
- Readiness: `http://localhost:8000/health/ready`

---

## 11. Production Cloud Deployment Guide

Q-FLOW is architected for containerized cloud deployment across modern hosting platforms:
- **Database**: Managed PostgreSQL on Supabase, Neon, AWS RDS, or Render PostgreSQL.
- **Backend**: Container deployment on Render, Railway, Fly.io, or AWS ECS.
- **Frontend**: Static SPA deployment on Vercel, Netlify, or Cloudflare Pages with proxy rewrites.
- For complete step-by-step instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 12. Verified Demo Credentials

| Role | Email / Identifier | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Receptionist / Staff** | `receptionist1@cityhealth.com` | `password123` | Queue control, emergency insertion, doctor delays |
| **General Staff** | `staff@qflow.com` | `password123` | Multi-department queue management |
| **Patient Demo** | `patient@qflow.com` | `password123` | Patient ticket tracking, arrival optimization |

---

## 13. Guided Demo Flow

### Patient Experience
1. Navigate to `http://localhost:5173/` and click **Check In & Join Queue**.
2. Register a new patient account or log in with `patient@qflow.com`.
3. Select **City Health General Hospital** -> **Cardiology** -> **Dr. Sarah Jenkins** -> **Morning OPD**.
4. Confirm queue entry in the pre-join conversion modal.
5. Review your live digital ticket (`/ticket/:entryId`), assigned token (e.g. `Q001`), estimated consultation window, and click **Why this estimate?** to inspect factors.
6. Click **Set Starting Point** -> select travel mode -> view your tailored **Arrival Plan** with recommended leave-by time.

### Staff Operations & Real-Time Reforecasting
1. In a separate tab or window, open `http://localhost:5173/staff` and log in as `receptionist1@cityhealth.com`.
2. Select **Cardiology - Dr. Sarah Jenkins OPD** to enter the Queue Control Center.
3. Observe live patient queue order.
4. Click **Doctor Delay** -> add 15 minutes -> click **Apply Doctor Delay**.
5. Switch to the patient ticket tab: observe the dynamic ETA banner update in real time via WebSocket without page refresh!
6. Click **Emergency Insert** in the staff console to observe priority elevation and instantaneous queue reforecasting.

---

## 14. Known Limitations & Future Work

1. **Synthetic Training Foundation**: The current duration model was trained on synthetic data due to cold database state; retraining pipeline should run once real completed consultations accumulate.
2. **External Transit**: Fallback mock provider calculates geodesic travel times; production deployment requires a Google Routes API key for live traffic congestion models.
3. **SMS Alerts**: Configured in development to mock provider; requires Twilio account credentials for direct SMS dispatch.
