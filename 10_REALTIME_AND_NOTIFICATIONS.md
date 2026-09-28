# Q-FLOW — Real-Time WebSocket & Notification Subsystem

## 1. Overview & Objective
Phase 6 establishes Q-FLOW's reactive operational backbone:
$$\text{Queue Action} \rightarrow \text{Queue Event} \rightarrow \text{Reforecast} \rightarrow \text{Prediction Snapshot} \rightarrow \text{Arrival Plan} \rightarrow \text{WebSocket Broadcast} \rightarrow \text{Notification Intent} \rightarrow \text{Patient Alert}$$

The real-time layer is designed around three strict non-negotiable principles:
1. **Transaction Authority Precedence**: WebSocket updates and notification intents are dispatched **strictly after** the authoritative database transaction commits.
2. **Strict Patient Isolation**: Patients can connect to and receive updates *only* for their own queue ticket (`WS /api/v1/ws/patient/{entry_id}`). They can never monitor or receive updates for another patient's ticket.
3. **Failure Decoupling**: WebSocket disconnects, slow network sockets, or notification delivery failures **never** cause database rollbacks or interrupt core OPD queue operations.

---

## 2. Database Schema & Migration

### Migration `347d1479409f`
Adds the following columns and constraints to the `notifications` table:
- `trigger_event_id`: UUID foreign key referencing `queue_events(id)` on delete `SET NULL`, indexed.
- `title`: `VARCHAR(255)`, nullable=False.
- `message`: `TEXT`, nullable=False.
- `payload_json`: `JSONB`, default `{}`, containing patient-safe operational metadata.
- `failure_reason`: `TEXT`, nullable=True.
- Unique constraint `uq_notifications_entry_trigger_type` on `(queue_entry_id, trigger_event_id, notification_type)` enforcing deterministic idempotency.

---

## 3. Real-Time WebSocket Architecture

### Endpoints
1. **Patient WebSocket**: `WS /api/v1/ws/patient/{entry_id}`
   - **Authentication**: JWT Bearer token extracted from `?token=<jwt>` query parameter or `Authorization: Bearer <jwt>` WebSocket headers.
   - **Authorization**: Strict patient isolation. A patient user may only connect to their own active `QueueEntry`. Any attempt by Patient B to connect to Patient A's entry is immediately rejected with close code `1008` (Policy Violation). Staff and Admins may inspect any patient's ticket.
   - **Initial Handshake & Reconnect**: On connect or reconnect, the server sends:
     1. `QUEUE_CONNECTED`: Handshake confirmation message with `entry_id` and `queue_id`.
     2. `QUEUE_SNAPSHOT`: Complete authoritative snapshot containing current queue status, token display, patient status, 1-indexed position, patients ahead, latest prediction window, and latest arrival plan.
   - **Privacy Guarantee**: Patient WebSocket messages **never** include origin coordinates (`origin_latitude`, `origin_longitude`) or PII of any other patient in the queue.

2. **Staff Queue Monitor**: `WS /api/v1/ws/queue/{queue_id}`
   - **Authentication**: JWT Bearer token required.
   - **Authorization**: Restricted to `STAFF` and `ADMIN` roles. Patients are rejected with close code `1008`.
   - **Initial Handshake**: On connect, returns `QUEUE_CONNECTED` followed by `QUEUE_SNAPSHOT` representing the Reception Control Center operational board (`waiting_count`, `currently_serving`, `currently_called`, `next_patient`, `completed_count`, `no_show_count`).

### `ConnectionManager`
- In-memory async connection pool tracking active connections grouped by `entry_id` and `queue_id`.
- Reconnect resilience: Automatically delivers fresh authoritative state upon client reconnection.
- Automatic stale cleanup: Sockets that fail during `send_json` are automatically removed from the registry without raising exceptions to callers.
- Thread-safe concurrency via `asyncio.Lock`.

---

## 4. Notification Intent & Dispatcher Subsystem

### Threshold & Idempotency Rules
- **Meaningful Change Threshold**: Notifications are dispatched **only** when `is_meaningful_change is True` or `abs(shift_minutes) >= 10`. Minor 1–2 minute jitter never triggers notifications.
- **Deterministic Deduplication**: Deduplicated by `(queue_entry_id, trigger_event_id, notification_type)`. If an alert has already been generated for the given trigger event, duplicate dispatches are skipped.
- **Audit Persistence**: Every evaluated notification is persisted in the database with status `PENDING`, transitioning to `SENT` or `FAILED`.
- **Decoupled Execution**: Provider delivery errors are caught, logged, and recorded on `notifications.failure_reason` without raising exceptions to the reforecast engine or rolling back queue transactions.

### Provider Interface & Mock Implementation
- `BaseNotificationProvider`: Abstract base class defining `async send(payload: NotificationPayload) -> bool`.
- `MockNotificationProvider`: In-memory provider for local development and CI testing. Records all sent notifications in `sent_notifications` and supports simulated failure via `should_fail = True`.
- Production SMS/Twilio provider is pluggable via dependency injection.

---

## 5. Security & Privacy Guarantees
- **No Token / Secret Leaks**: JWT tokens and API keys are never echoed back in WebSocket payloads or logs.
- **Location Privacy**: GPS origin coordinates (`origin_latitude`, `origin_longitude`) are strictly transient on `QueueEntry` and are scrubbed from all WebSocket snapshots, notifications, and event logs.
- **Strict Role-Based Access Control**: Only authorized users can connect to WebSocket channels. Staff endpoints reject patient tokens.
