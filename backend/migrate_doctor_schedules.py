"""Migration script to create doctor_schedules table and add columns to arrival_plans."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "qflow.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Create doctor_schedules table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS doctor_schedules (
    id VARCHAR(36) PRIMARY KEY,
    hospital_id VARCHAR(36) NOT NULL,
    doctor_id VARCHAR(36) NOT NULL,
    department_id VARCHAR(36) NOT NULL,
    schedule_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'AVAILABLE',
    created_by_staff_id VARCHAR(36),
    opd_session_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_doctor_schedule_date UNIQUE (doctor_id, schedule_date),
    FOREIGN KEY(hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    FOREIGN KEY(doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE CASCADE,
    FOREIGN KEY(created_by_staff_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(opd_session_id) REFERENCES opd_sessions(id) ON DELETE SET NULL
)
""")

cursor.execute("CREATE INDEX IF NOT EXISTS ix_doctor_schedules_hosp_date ON doctor_schedules (hospital_id, schedule_date)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_doctor_schedules_doc_date ON doctor_schedules (doctor_id, schedule_date)")

# 2. Add columns to arrival_plans if they don't exist
cursor.execute("PRAGMA table_info(arrival_plans)")
columns = [row[1] for row in cursor.fetchall()]

new_cols = [
    ("driving_distance_meters", "INTEGER"),
    ("bike_duration_seconds", "INTEGER"),
    ("bike_distance_meters", "INTEGER"),
    ("selected_travel_mode", "VARCHAR(30) DEFAULT 'DRIVE' NOT NULL"),
]

for col_name, col_type in new_cols:
    if col_name not in columns:
        print(f"Adding column {col_name} to arrival_plans...")
        cursor.execute(f"ALTER TABLE arrival_plans ADD COLUMN {col_name} {col_type}")

# 3. Retain the authoritative schedule and selected appointment time on every
# queue entry. SQLite cannot add the FK constraint retrospectively, but the
# application migration supplies it for managed databases.
cursor.execute("PRAGMA table_info(queue_entries)")
entry_columns = [row[1] for row in cursor.fetchall()]
for col_name, col_type in [
    ("schedule_id", "VARCHAR(36)"),
    ("appointment_time", "TIME"),
]:
    if col_name not in entry_columns:
        print(f"Adding column {col_name} to queue_entries...")
        cursor.execute(f"ALTER TABLE queue_entries ADD COLUMN {col_name} {col_type}")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_queue_entries_schedule_id ON queue_entries (schedule_id)")

# 4. Backfill the explicit operational date for legacy queues from OPD sessions.
cursor.execute("PRAGMA table_info(queues)")
queue_columns = [row[1] for row in cursor.fetchall()]
if "queue_date" not in queue_columns:
    print("Adding column queue_date to queues...")
    cursor.execute("ALTER TABLE queues ADD COLUMN queue_date DATE")
    cursor.execute("UPDATE queues SET queue_date = DATE((SELECT starts_at FROM opd_sessions WHERE opd_sessions.id = queues.opd_session_id)) WHERE queue_date IS NULL")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_queues_date ON queues (queue_date)")

conn.commit()
conn.close()
print("Migration completed successfully!")
