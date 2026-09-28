# Q-FLOW — Travel-Aware Arrival Optimization

## 1. Purpose & Core Philosophy
The purpose of Q-FLOW's Arrival Optimization layer is NOT merely answering "How long does it take to reach the hospital?"
Rather, it solves the patient's critical decision:
> **"When should I leave home so that I arrive at the hospital at the right time for my predicted consultation window?"**

By bridging real-time queue forecasting with transit duration and uncertainty, Q-FLOW eliminates wasted waiting in crowded waiting rooms while ensuring patients arrive before their consultations begin.

---

## 2. Core Architecture
The arrival optimizer is completely decoupled from the queue state machine:
```text
Queue Engine (Authoritative Queue State)
       ↓
Prediction Engine (Consultation Window: [predicted_start_at, predicted_end_at])
       ↓
Travel Provider (BaseTravelProvider -> GoogleRoutesProvider / MockTravelProvider)
       ↓
Travel Estimate (duration, uncertainty, distance)
       ↓
Arrival Optimizer (ArrivalOptimizationService)
       ↓
Arrival Plan (Recommended Arrival & Departure Windows)
       ↓
Patient & Staff REST APIs
```

- **Read-Only / Advisory Invariant:** The arrival optimizer never modifies queue state, tokens, or prediction snapshots. It consumes prediction snapshots and produces auditable, linked `ArrivalPlan` records.

---

## 3. Travel Provider Abstraction & Selection Hierarchy
Q-FLOW interfaces with transit services via `BaseTravelProvider`:
- **`MockTravelProvider`**: Deterministic, configurable transit simulator used in CI and local testing without incurring API fees or network dependencies.
- **`GoogleRoutesProvider`**: Production integration with Google Routes API v2 (`https://routes.googleapis.com/directions/v2:computeRoutes`). Computes duration, static duration, route distance, and traffic variance.
- **Canonical API Key Configuration**:
  - Primary canonical key: `GOOGLE_ROUTES_API_KEY`.
  - Legacy backwards-compatible alias: `GOOGLE_MAPS_API_KEY`.
  - Keys are strictly kept in environment variables or `.env`; never logged, never returned in API payloads, never committed.
- **Provider Selection Hierarchy**:
  1. **Production**: `GOOGLE_ROUTES_API_KEY` configured and valid -> `GoogleRoutesProvider`.
  2. **Local/Test**: Key intentionally absent -> `MockTravelProvider` (`travel_provider = "mock"`, explanation `"Development travel estimate."`).
  3. **External Provider Failure**: Configured Google API fails due to timeout, 4xx/5xx, quota exhaustion, network issue, or malformed response ->
     - **NEVER** silently claims `google_routes` or `OPTIMIZED`.
     - Returns `travel_status = "DEGRADED"` (or `"UNAVAILABLE"`) with `travel_provider = "mock"`.
     - Provides clean patient explanation: `"Travel estimate temporarily unavailable. Your consultation estimate is still available."`
     - Technical errors and secrets are never surfaced to patients.

---

## 4. Travel Cache & API Cost Protection
To prevent repeated expensive external API calls:
- **`TravelCache`**: Thread-safe in-memory cache.
- **Time-Bucketed Key**:
  `{round(origin_lat, 4)},{round(origin_lng, 4)}->{round(dest_lat, 4)},{round(dest_lng, 4)}:{travel_mode}:{time_bucket}`
  Coordinates are rounded to 4 decimal places (~11 meters). Departure time is bucketed into 5-minute intervals (`epoch // 300`).
- **Configurable TTL**: Default `600 seconds` (10 minutes). Repeated requests within this window are served instantaneously from cache.

---

## 5. Mathematical Formulations & Semantics

### Distinct Semantic Windows
Q-FLOW enforces three strictly distinct temporal concepts:
1. **Estimated Consultation Window:** When clinical consultation is expected to occur (`[predicted_start_at — predicted_end_at]`).
2. **Recommended Arrival Window:** When the patient should physically arrive at the hospital reception (`[arrival_start_at — arrival_end_at]`).
3. **Recommended Departure Window:** When the patient should depart their origin location (`[departure_start_at — departure_end_at]`).

### Exact Mathematical Formulas
Let:
- $T_{\text{start}} = \text{predicted\_start\_at}$
- $B = \text{arrival\_buffer\_seconds}$ (default $600\text{ s} = 10\text{ min}$)
- $\Delta B = 300\text{ s}$ (5-minute buffer half-window)
- $D = \text{travel\_duration\_seconds}$
- $U = \text{travel\_uncertainty\_seconds}$ (derived from Google traffic delta or mock variance, minimum $300\text{ s}$)

#### Recommended Arrival Window
$$\text{arrival\_end\_at} = T_{\text{start}} - (B - \Delta B) = T_{\text{start}} - 300\text{ s} \quad (5\text{ minutes before consultation starts})$$
$$\text{arrival\_start\_at} = T_{\text{start}} - (B + \Delta B) = T_{\text{start}} - 900\text{ s} \quad (15\text{ minutes before consultation starts})$$

#### Recommended Departure Window
$$\text{total\_travel\_allocation} = D + U$$
$$\text{departure\_start\_at} = \text{arrival\_start\_at} - \text{total\_travel\_allocation}$$
$$\text{departure\_end\_at} = \text{arrival\_end\_at} - \text{total\_travel\_allocation}$$

#### Example Verification:
- Consultation Window: 4:35 PM – 4:55 PM ($T_{\text{start}} = \text{4:35 PM}$)
- Travel Duration: 30 minutes ($D = 1800\text{ s}$), Uncertainty: 5 minutes ($U = 300\text{ s}$) $\implies$ total allocation = 35 minutes
- **Recommended Arrival Window:** 4:20 PM – 4:30 PM
- **Recommended Departure Window:** 3:45 PM – 3:55 PM

---

## 6. Meaningful Change Threshold (10 Minutes)
Reusing Q-FLOW's 10-minute threshold:
- If consultation window start shifts by $\ge 10$ minutes: `consultation_changed = True`.
- If departure window start shifts by $\ge 10$ minutes: `travel_changed = True`.
- `is_meaningful_change = consultation_changed or travel_changed`.
- Minor fluctuations ($< 10$ minutes) do not flag meaningful change, preventing client notification fatigue.

---

## 7. Dynamic Reforecasting Integration
When operational queue disruptions occur (`EMERGENCY_INSERTED`, `DOCTOR_DELAY`, `PATIENT_NO_SHOW`, etc.):
1. Prediction engine recalculates the downstream consultation window and appends a `PredictionSnapshot`.
2. The arrival optimizer checks if the patient has configured travel coordinates (`origin_latitude`, `origin_longitude`).
3. If configured, a new `ArrivalPlan` is automatically generated referencing the new snapshot, with updated departure windows and context-aware explanation.

---

## 8. Location Privacy & Lifecycle
- **Transient Association:** Origin coordinates are saved on `QueueEntry` as transient operational data for the ticket.
- **Strict Privacy Invariants:**
  - Origin coordinates are **never** logged in application logs.
  - Coordinates are **never** included in queue snapshots, queue events, or prediction explanations.
  - Patients can **never** view or mutate another patient's travel origin or arrival plan (HTTP 403 Forbidden).
  - Coordinates are automatically cascade-deleted when the queue ticket is purged.

---

## 9. Failure Resilience & Status Transparency
Q-FLOW clearly distinguishes between three travel states to ensure complete transparency:
- **`OPTIMIZED`**: Calculated from live traffic data (Google Routes v2) or active developmental configuration.
- **`DEGRADED`**: External provider (Google Routes) failed due to network timeout, HTTP error (4xx/5xx), quota limit, or malformed payload. The system falls back to deterministic local calculation without fabricating fake traffic data, clearly marking `travel_provider = "mock"`, `travel_status = "DEGRADED"`, and patient explanation: *"Travel estimate temporarily unavailable. Your consultation estimate is still available."*
- **`UNAVAILABLE`**: No starting coordinates provided, or coordinates are incomplete. Consultation estimates remain available, and guidance asks the patient to enter their origin.

In all failure scenarios, queue operations, tokens, and prediction snapshots are never blocked or corrupted.
