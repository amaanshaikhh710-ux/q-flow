# Q-FLOW — Database Schema

**Status:** FROZEN FOR MVP. Database engine: **PostgreSQL** with SQLAlchemy ORM, Alembic migrations, and JSONB.

## Relationship
```text
HOSPITAL → DEPARTMENT → DOCTOR → OPD_SESSION → QUEUE → QUEUE_ENTRY → CONSULTATION
                                                   └→ QUEUE_EVENT
```

## `hospitals`
Purpose: participating hospital.
- `id` BIGINT/UUID PK
- `name` VARCHAR NOT NULL
- `address` VARCHAR/TEXT
- `latitude` DECIMAL TBD
- `longitude` DECIMAL TBD
- `created_at`, `updated_at` TIMESTAMP

## `departments`
Purpose: OPD/department.
- `id` PK
- `hospital_id` FK → hospitals.id
- `name` VARCHAR NOT NULL
- timestamps
Index: `(hospital_id, name)`

## `users`
Purpose: application accounts.
- `id` PK
- `name` VARCHAR NOT NULL
- `phone` VARCHAR unique where required
- `email` VARCHAR unique where required
- `password_hash` VARCHAR; never plaintext (bcrypt)
- `role` VARCHAR/ENUM (patient/staff/admin)
- `hospital_id` nullable FK → hospitals.id (Index: `ix_users_hospital_id`). Required for staff members to scope operations strictly to their hospital.
- timestamps

## `doctors`
Purpose: doctor identity/availability.
- `id` PK
- `department_id` FK
- `name` VARCHAR NOT NULL
- `status` VARCHAR/ENUM (available/unavailable/break)
- timestamps

## `opd_sessions`
Purpose: operational session.
- `id` PK
- `department_id` FK
- `doctor_id` FK
- `starts_at`, `ends_at` TIMESTAMP
- `status` (scheduled/active/paused/completed/cancelled)
- timestamps
Index `(doctor_id, starts_at)`

## `queues`
Purpose: concurrent queue.
- `id` PK
- `opd_session_id` FK
- `name` VARCHAR
- `status` active/paused/completed
- `current_position` optional cache; never sole source of truth
- timestamps

## `queue_entries`
Purpose: patient participation.
- `id` PK
- `queue_id` FK
- `patient_user_id` FK → users.id
- `token_number` unique within queue/session (guaranteed identical sequence for online and staff bookings)
- `priority_class` normal/priority/emergency
- `status` state-machine value (BOOKED, ARRIVED, WAITING, CALLED, IN_CONSULTATION, COMPLETED, TEMPORARILY_LEFT, RETURNED, NO_SHOW)
- `booking_source` VARCHAR(30) default 'ONLINE' ('ONLINE', 'STAFF', 'WALK_IN', 'PHONE')
- `notes` TEXT nullable (clinical triage / check-in notes)
- `joined_at` TIMESTAMP NOT NULL
- `arrived_at` nullable TIMESTAMP
- `called_at` nullable TIMESTAMP
- `temporary_left_at` nullable TIMESTAMP
- `returned_at` nullable TIMESTAMP
- `no_show_at` nullable TIMESTAMP
- timestamps
Indexes `(queue_id,status)`, `(queue_id,token_number)`, `(patient_user_id,created_at)`

*(Note: Consultation lifecycle start/end timestamps are normalized into the dedicated `consultations` table below).*

## `consultations`
Purpose: primary source of truth for clinical consultation records and durations.
- `id` PK (BIGINT/UUID)
- `queue_entry_id` FK → queue_entries.id UNIQUE NOT NULL
- `doctor_id` FK → doctors.id NOT NULL
- `started_at` TIMESTAMP NOT NULL
- `completed_at` TIMESTAMP nullable
- `duration_seconds` INT nullable (recorded upon completion)
- `interruption_notes` TEXT nullable
- `created_at`, `updated_at` TIMESTAMP
Indexes `(doctor_id, started_at)`, `(queue_entry_id)`

## `queue_events`
Purpose: append-only operational history, reconstruction, audit and model data.
- `id` PK
- `queue_id` FK
- `queue_entry_id` nullable FK
- `actor_user_id` nullable FK
- `event_type` VARCHAR/ENUM
- `event_time` TIMESTAMP
- `payload_json` JSONB
- `created_at`
Indexes `(queue_id,event_time)`, `(queue_entry_id,event_time)`, `(event_type,event_time)`

Event types include: TOKEN_CREATED, PATIENT_JOINED, PATIENT_CHECKED_IN, PATIENT_CALLED, CONSULTATION_STARTED, CONSULTATION_COMPLETED, PRIORITY_INSERTED, EMERGENCY_INSERTED, DOCTOR_BREAK_STARTED/ENDED, DOCTOR_DELAY, QUEUE_PAUSED/RESUMED, PATIENT_NO_SHOW, PATIENT_TEMPORARILY_LEFT, PATIENT_RETURNED, DOCTOR_UNAVAILABLE, DOCTOR_AVAILABLE.

## `notifications`
Purpose: delivery tracking.
- `id` PK
- `user_id` FK
- `queue_entry_id` nullable FK
- `channel` SMS/WHATSAPP/WEB
- `notification_type`
- `content_reference` or approved content fields
- `status` (pending/sent/delivered/failed)
- `sent_at`, `delivered_at`, `failed_at`
- `created_at`

## `otp_tokens`
Purpose: temporary one-time password tokens for patient authentication and self-registration.
- `id` PK (UUID)
- `recipient` VARCHAR(255) NOT NULL (phone or email, indexed)
- `otp_code` VARCHAR(64) NOT NULL (6-digit numeric OTP)
- `purpose` VARCHAR(50) NOT NULL default 'LOGIN'
- `expires_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `is_verified` BOOLEAN NOT NULL default FALSE
- `created_at` TIMESTAMP WITH TIME ZONE NOT NULL
Index: `(recipient, is_verified)`

## Consultation record decision: RESOLVED
Use a dedicated normalized `consultations` table as the primary source of truth for consultation records and timestamps. `queue_events` remains the append-only event/audit source.

## Business rules
1. Event history is retained.
2. Cached queue state is not the only source of truth.
3. Real long consultations are not erased from live state.
4. Emergency is a queue event/class, not merely an outlier.
5. No-show changes downstream ETA.
6. Doctor delay/break changes availability and ETA.
7. Queues have independent mutable state.
8. Authorization prevents cross-hospital access.
9. Cascade/delete policy is TBD and must be explicit before production migrations.
