# Q-FLOW — API Specification

Exact routes were not finalized in the planning discussion. The following are the **proposed implementation contract** derived from the agreed requirements. If implementation changes a route, update this document and the changelog.

## Conventions
- Proposed base: `/api/v1`
- JSON over HTTPS
- Auth/role checks server-side
- Every staff queue mutation creates an event
- Validation at API boundary

## Auth
### POST `/api/v1/auth/register`
Patient registration. Request: name, phone/email, password. Public registration is strictly coerced to role `patient`.

### POST `/api/v1/auth/login`
Request: identifier + password. Returns JWT access token and user role.

### POST `/api/v1/auth/otp/request`
Request: `recipient` (phone or email), `purpose` (default: "LOGIN"). Generates a 6-digit numeric OTP code with 10-minute expiry. Dispatches via configured SMS/Email provider or logs for development with honest status reporting (`CONFIGURATION REQUIRED` if external gateway credentials not configured).

### POST `/api/v1/auth/otp/verify`
Request: `recipient`, `otp_code`, optional `name`. Verifies OTP token. If recipient is an existing user, logs in and returns access token. If new user, automatically self-registers them with role `patient` and returns access token.

### POST `/api/v1/auth/logout`
Invalidates session where supported.

## Discovery
### GET `/hospitals`
List available hospitals.
### GET `/hospitals/{hospital_id}/departments`
List departments.
### GET `/departments/{department_id}/doctors`
List doctors/queues available for selection.
### GET `/api/v1/discovery/staff-hospital`
Staff operation (STAFF or ADMIN role): returns the authenticated staff member's assigned hospital, associated departments, and active queues. Enforces hospital scoping.

## Patient & Queue Endpoints
### POST `/api/v1/queues/{queue_id}/join`
Creates queue entry and server-allocated token (e.g. `Q001`). Requires PATIENT (or STAFF/ADMIN).
- Atomically computes sequential token via `SELECT ... FOR UPDATE`.
- Rejects duplicate active joins for the same patient with HTTP 409 Conflict.
- Logs `PATIENT_JOINED` event.

### GET `/api/v1/queues/{queue_id}`
Returns authoritative queue metadata.

### GET `/api/v1/queues/{queue_id}/snapshot`
Authoritative current state of the queue:
- Serving patient (`IN_CONSULTATION`)
- Called patient (`CALLED`)
- Next eligible patient (`WAITING`, position 1)
- Ordered waiting list with 1-indexed positions
- Aggregate counts: `total_waiting`, `total_in_consultation`, `total_completed`, `total_no_show`
- Clinical provider metadata (doctor name, department)

### GET `/api/v1/queue-entries/{entry_id}`
Returns authoritative entry details, server-calculated position, and status.
- Patients can only view their own tickets; staff and admins can view any.

### GET `/api/v1/queue-entries/my`
Patient operation: returns all appointments for the authenticated patient categorized into `today`, `upcoming`, and `past` with rich hospital, doctor, estimated wait, and travel plan metadata. Strict patient isolation enforced.

## Staff Operations (STAFF or ADMIN role required — Hospital-Scoped)
All staff operations strictly enforce hospital-scoped authorization (`verify_staff_hospital_access`). Staff members attempting to operate on queues outside their assigned `hospital_id` are denied with HTTP 403 Forbidden.

### POST `/api/v1/queues/{queue_id}/staff-book`
Staff operation (walk-in, phone, or reception desk): books a patient into the target active queue using the **exact same queue numbering sequence** as online patient bookings. Atomically allocates the next sequential token using `SELECT ... FOR UPDATE` and optimistic retry. Emits `PATIENT_JOINED` or `APPOINTMENT_BOOKED` audit event with `actor_user_id = staff_user_id` and records `booking_source` ('WALK_IN', 'PHONE', 'STAFF') and `notes`. Walk-in entries are initialized in `WAITING` state with `arrived_at = now`; phone entries are initialized in `BOOKED` state.

### POST `/api/v1/queue-entries/{entry_id}/arrive`
Staff operation: marks physical arrival of a patient at the hospital OPD desk (`BOOKED` -> `ARRIVED`). Sets `arrived_at` timestamp and emits `PATIENT_ARRIVED` audit event.

### POST `/api/v1/queue-entries/{entry_id}/wait`
Staff operation: advances an arrived patient into the active waiting queue (`ARRIVED` -> `WAITING`), making them eligible to be called. Emits `CHECKED_IN` audit event.

### POST `/api/v1/queues/{queue_id}/call-next`
Determines and calls next eligible patient according to priority rank and arrival order (`WAITING` -> `CALLED`, position becomes 0). Logs `PATIENT_CALLED`.

### POST `/api/v1/queue-entries/{entry_id}/call`
Calls specific eligible patient in `WAITING` state. Logs `PATIENT_CALLED`.

### POST `/api/v1/queue-entries/{entry_id}/start-consultation`
Transitions patient from `CALLED` to `IN_CONSULTATION`.
- Creates record in dedicated normalized `consultations` table with `started_at` and `doctor_id` (DEC-031).
- Logs `CONSULTATION_STARTED`.

### POST `/api/v1/queue-entries/{entry_id}/complete-consultation`
Transitions patient from `IN_CONSULTATION` to `COMPLETED`.
- Finalizes record in `consultations` table with `completed_at` and `duration_seconds` (DEC-031).
- Logs `CONSULTATION_COMPLETED`.

### POST `/api/v1/queue-entries/{entry_id}/leave`
Staff operation: records patient temporary departure (`WAITING` -> `TEMPORARILY_LEFT`). Excluded from active calling order. Logs `PATIENT_TEMPORARILY_LEFT`.

### POST `/api/v1/queue-entries/{entry_id}/return`
Staff operation: records patient return (`TEMPORARILY_LEFT` -> `RETURNED`). Awaits staff re-queueing. Logs `PATIENT_RETURNED`.

### POST `/api/v1/queue-entries/{entry_id}/no-show`
Transitions `WAITING` or `CALLED` patient to `NO_SHOW`. Logs `PATIENT_NO_SHOW`.

### POST `/api/v1/queue-entries/{entry_id}/requeue`
Staff actively requeues a `RETURNED` patient back into active `WAITING` state (DEC-033). Preserves original token number. Logs `STAFF_REQUEUES`.

### POST `/api/v1/queue-entries/{entry_id}/priority`
Changes priority rank of waiting patient (`NORMAL` / `PRIORITY` / `EMERGENCY`). Recalculates waiting sequence without altering token identities. Logs `PRIORITY_CHANGED` (or `EMERGENCY_INSERTED`).

### POST `/api/v1/queues/{queue_id}/emergency`
Atomically inserts a new emergency patient into the queue with highest priority rank (`EMERGENCY`). Allocates next sequential token and places patient at position 1. Logs `EMERGENCY_INSERTED`.

### POST `/api/v1/queues/{queue_id}/doctor-delay`
Records doctor operational disruption with delay duration in minutes. Logs `DOCTOR_DELAY`.

### POST `/api/v1/queues/{queue_id}/doctor-break/start` and `/doctor-break/end`
Records doctor break interval. Logs `DOCTOR_BREAK_STARTED` and `DOCTOR_BREAK_ENDED`.

### POST `/api/v1/queues/{queue_id}/pause` and `/resume`
Controls queue state (`ACTIVE` / `PAUSED`). Logs `QUEUE_PAUSED` and `QUEUE_RESUMED`.

### GET `/api/v1/hospital/historical-appointments`
Staff operation (STAFF or ADMIN role): returns paginated historical appointments for the staff member's assigned hospital.
- **Parameters:**
  - `date_preset`: `today`, `yesterday`, `this_week`, `last_week`, `this_month`
  - `start_date`, `end_date`: Custom date range filter (ISO date format)
  - `doctor_id`, `department_id`, `queue_id`: Structural filters
  - `status`: Filter by appointment status (`BOOKED`, `ARRIVED`, `WAITING`, `IN_CONSULTATION`, `COMPLETED`, `NO_SHOW`, etc.)
  - `booking_source`: Filter by source (`ONLINE`, `PHONE`, `WALK_IN`, `STAFF`)
  - `skip`, `limit`: Server-side pagination
- **Enforces hospital scoping:** Staff can only query historical records for their assigned hospital (`403 Forbidden` on cross-hospital access).

### GET `/api/v1/hospital/historical-appointments/export`
Staff operation (STAFF or ADMIN role): streams a filtered CSV export of historical appointments matching the applied query parameters for the staff member's assigned hospital.

## Prediction
### GET `/api/v1/queue-entries/{entry_id}/prediction`
Returns the latest **Estimated Consultation Window** for a queue entry. Accessible by Patient (for own entry only) and Staff/Admin.
Response Schema (`PredictionResponse`):
- `predicted_start_at`: Earliest/central expected consultation start time according to server queue calculation. (Not a fixed appointment).
- `predicted_end_at`: Expected completion boundary including uncertainty margin (`predicted_start_at + duration + margin`). Always strictly greater than `predicted_start_at`.
- `uncertainty_margin_seconds`: Non-negative buffer in seconds (`>= 180s`, default `300s`), derived from historical MAD.
- `predicted_duration_seconds`: Non-negative estimated service duration in seconds (`>= 60s`, default `900s`).
- `patients_ahead_count`: Non-negative count of active unserviced patients ahead in queue.
- `explanation`: Human-readable context explanation for the estimate or dynamic reforecast.
- `model_version`: Model identifier string (`baseline-v1`).
- *Integrity Rule:* No fake confidence percentages are exposed.

### GET `/api/v1/queue-entries/{entry_id}/prediction/history`
Returns chronological list of all prediction snapshots for this entry, showing how ETAs and uncertainty windows evolved as queue disruptions occurred. Accessible by Patient (for own entry) and Staff/Admin.

### GET `/api/v1/queues/{queue_id}/predictions`
Returns full queue prediction board with latest prediction snapshot for each active waiting/called entry in the queue. Restricted to Staff/Admin.

### POST `/api/v1/queues/{queue_id}/reforecast`
Triggers an immediate reforecast calculation across all active entries in the queue. Restricted to Staff/Admin.



## Travel & Arrival Optimization
### POST `/api/v1/queue-entries/{entry_id}/travel-origin`
Sets or updates the patient's transient starting coordinates (`latitude`, `longitude`, `travel_mode`). Validates latitude $\in [-90, 90]$ and longitude $\in [-180, 180]$. Immediately computes and returns the updated `ArrivalPlanResponse`. Accessible by Patient (own ticket only) and Staff/Admin.

### GET `/api/v1/queue-entries/{entry_id}/travel`
Returns latest direct transit duration and uncertainty estimate from the travel provider (`GoogleRoutesProvider` using canonical `GOOGLE_ROUTES_API_KEY`, or `MockTravelProvider`), utilizing time-bucketed caching. Returns `travel_status = "OPTIMIZED"`, `"DEGRADED"`, or `"UNAVAILABLE"` (if no origin has been set). Accessible by Patient (own ticket only) and Staff/Admin.

### GET `/api/v1/queue-entries/{entry_id}/arrival-plan`
Returns the latest travel-aware arrival and departure optimization recommendation (`ArrivalPlanResponse`):
- `travel_provider`: `"google_routes"` or `"mock"` (never claims Google when degraded)
- `travel_status`: `"OPTIMIZED"`, `"DEGRADED"`, or `"UNAVAILABLE"`
- `consultation_start_at`, `consultation_end_at`: Estimated Consultation Window
- `arrival_start_at`, `arrival_end_at`: Recommended Arrival Window
- `departure_start_at`, `departure_end_at`: Recommended Departure Window (null if `UNAVAILABLE`)
- `travel_duration_seconds`, `travel_uncertainty_seconds`: Transit estimate
- `is_meaningful_change`, `consultation_changed`, `travel_changed`: Shift flags ($\ge 10$ minutes)
- `explanation`: Patient-facing departure recommendation text (clean messages without raw exceptions)
Accessible by Patient (own ticket only) and Staff/Admin.

### GET `/api/v1/queue-entries/{entry_id}/arrival-plan/history`
Returns complete chronological audit history of arrival plans for the ticket, illustrating how departure windows updated as queue conditions changed. Accessible by Patient (own ticket only) and Staff/Admin.


## Notifications
### GET `/notifications`
Returns authorized notification history.
### POST `/notifications/test`
Development/admin only.

## Real-Time WebSocket API (Phase 6 Implemented)

### Base Path: `/api/v1/ws`

### 1. Patient Ticket Live Channel: `WS /api/v1/ws/patient/{entry_id}`
- **Authentication**: JWT Bearer token supplied via query parameter (`?token=<jwt>`) or standard `Authorization: Bearer <jwt>` WebSocket headers.
- **Authorization**: Strict patient isolation. A patient may connect only to their own active queue entry. Connecting to another patient's ticket is rejected with close code `1008` (Policy Violation). Staff and Admins may inspect any ticket.
- **Handshake Sequence**:
  1. `QUEUE_CONNECTED`: Handshake confirmation (`type`, `version`, `timestamp`, `entry_id`, `queue_id`).
  2. `QUEUE_SNAPSHOT`: Initial state snapshot with current queue status, token display, patient status, 1-indexed position, patients ahead count, latest prediction window, and latest arrival plan.
- **Subsequent Messages**:
  - `QUEUE_REFORECAST`: Real-time updates emitted when upstream queue disruptions alter the patient's consultation window.
- **Privacy Guarantee**: Zero coordinates (`origin_latitude`, `origin_longitude`) and zero PII of other patients.

### 2. Staff Queue Board Channel: `WS /api/v1/ws/queue/{queue_id}`
- **Authentication**: JWT Bearer token required.
- **Authorization**: Restricted to `STAFF` and `ADMIN` roles. Patient connections rejected with close code `1008`.
- **Handshake Sequence**:
  1. `QUEUE_CONNECTED`: Handshake confirmation.
  2. `QUEUE_SNAPSHOT`: Reception Control Center queue monitor board (`queue_name`, `queue_status`, `doctor_name`, `department_name`, `currently_serving`, `currently_called`, `next_patient`, `waiting_count`, `completed_count`, `no_show_count`).
- **Subsequent Messages**:
  - `QUEUE_SNAPSHOT` and `QUEUE_REFORECAST` updates broadcast whenever queue state changes.

## Errors
Use 400 validation/business input, 401 unauthenticated, 403 unauthorized, 404 missing resource, 409 invalid state conflict, 422 schema validation where FastAPI conventions apply, 429 where rate limiting exists, 500 unexpected failure.

## API invariants
- Client cannot authoritatively reorder queues.
- Staff mutations create events.
- Prediction uses authoritative state.
- WebSocket broadcasts occur after successful state changes.
- Provider secrets never reach clients.
