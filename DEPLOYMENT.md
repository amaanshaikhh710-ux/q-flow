# Q-FLOW — Production Deployment Guide
**Target Environments**: Vercel/Netlify (Frontend), Render/Railway/Fly.io (Backend), Managed PostgreSQL (Neon/Supabase/RDS)

---

## 1. Architecture Overview

```
[ Patient / Staff Browser ]
           |
     HTTPS / WSS
           v
  [ Frontend: Vercel / Nginx ]
           |
     REST / WebSocket
           v
  [ Backend: FastAPI on Render / Fly.io / Container ]
      |                 |                   |
      v                 v                   v
[ Managed Postgres ]  [ Google Routes ]   [ SMS Provider ]
  (Neon / RDS)          (Server-side)       (Twilio / Mock)
```

---

## 2. Managed PostgreSQL Setup

1. Provision a PostgreSQL instance (v15 or v16) on Neon, Supabase, Railway, or AWS RDS.
2. Note your connection string:
   `postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require`
3. Execute database migrations using Alembic:
   ```bash
   cd backend
   alembic upgrade head
   ```
4. Verify migrations:
   ```bash
   alembic current
   # Expected output: 347d1479409f (head)
   ```

---

## 3. Backend Deployment (Render / Railway / Fly.io)

### Environment Variables
Set the following variables in your hosting dashboard:
- `APP_ENV`: `production`
- `DEBUG`: `False`
- `DATABASE_URL`: `postgresql://<user>:<password>@<host>:<port>/<dbname>`
- `JWT_SECRET`: A secure 64-character hex string generated via `openssl rand -hex 32`.
- `JWT_ALGORITHM`: `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: `1440`
- `CORS_ORIGINS`: `https://your-frontend.vercel.app`
- `GOOGLE_ROUTES_API_KEY`: Server-side Google API key with Routes API enabled.
- `SMS_PROVIDER`: `mock` (or `twilio` if credentials provided).

### Startup Command
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health Check Probes
- Liveness Probe: `GET /health` (Status 200)
- Readiness Probe: `GET /health/ready` (Status 200 when DB is connected)

---

## 4. Frontend Deployment (Vercel / Netlify)

### Environment Variables
Set in Vercel / Netlify dashboard:
- `VITE_API_BASE_URL`: `https://your-backend.onrender.com`

### Build Settings
- **Framework Preset**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Install Command**: `npm install`

### SPA Routing (Vercel `vercel.json` or Netlify `_redirects`)
For Netlify, add a `_redirects` file:
```text
/*    /index.html   200
```
For Vercel, `vercel.json`:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

## 5. Docker Deployment (Alternative Self-Hosted Option)

To run the entire stack locally or on a single VPS with Docker Compose:

1. Copy `.env.example` in backend and configure credentials.
2. Launch stack:
   ```bash
   docker-compose up -d --build
   ```
3. Check container logs:
   ```bash
   docker-compose logs -f backend
   ```
4. Access application:
   - Frontend: `http://localhost:5173`
   - Backend API: `http://localhost:8000`
   - Readiness Probe: `http://localhost:8000/health/ready`
