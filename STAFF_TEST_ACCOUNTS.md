# Q-FLOW Demo Staff Accounts

> All staff accounts are provisioned by the backend seed script (ackend/scripts/seed_demo.py).
> There is no public staff registration. Staff credentials are assigned by administration.

## Staff Accounts (One Per Hospital)

| Hospital | Location | Staff Name | Email | Password | Role |
|---|---|---|---|---|---|
| King Edward Memorial (KEM) Hospital | Parel, Mumbai | Sunil More | staff.kem@qflow.com | password123 | STAFF |
| BYL Nair Charitable Hospital | Mumbai Central | Pooja Varma | staff.nair@qflow.com | password123 | STAFF |
| Lokmanya Tilak Municipal General Hospital | Sion, Mumbai | Deepak Shinde | staff.sion@qflow.com | password123 | STAFF |
| Sir J.J. Group of Hospitals | Byculla, Mumbai | Anita Rane | staff.jj@qflow.com | password123 | STAFF |
| Rajawadi Municipal General Hospital | Ghatkopar, Mumbai | Girish Kadam | staff.rajawadi@qflow.com | password123 | STAFF |

## Demo Patient Account

| Email | Password |
|---|---|
| patient@qflow.com | password123 |

---

## Staff Portal Access

Each staff account is **permanently scoped** to exactly one hospital. When a staff member logs in:

1. The backend reads current_user.hospital_id from their JWT token
2. Only data belonging to that hospital is returned
3. Any attempt to access another hospital's data returns **HTTP 403 Forbidden**

## What Each Staff Account Can Do

- View their assigned hospital's OPD operations dashboard
- Manage all queues within their hospital (not other hospitals)
- Mark patients: Arrived -> Waiting -> Called -> In Consultation -> Completed
- Add walk-in and phone appointments (receive next sequential token)
- Trigger emergency insertions and doctor delays
- View and export historical appointment data (filtered to their hospital)

---

## Cross-Hospital Isolation Test

1. Log in as staff.kem@qflow.com - should see only KEM Hospital queues
2. Log in as staff.nair@qflow.com - should see only BYL Nair Hospital queues
3. GET /api/v1/discovery/staff-hospital with KEM token - returns KEM data regardless of query params
4. GET /api/v1/queues/<nair-queue-id>/snapshot with KEM token - HTTP 403 Forbidden

---

## Re-seeding

To reset all demo data:

    cd backend
    .venv\Scripts\python.exe scripts/seed_demo.py
