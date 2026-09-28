# Q-FLOW Demo Accounts Documentation

This document contains authoritative credentials for all demo patient and staff accounts seeded in the Q-FLOW environment for the hackathon presentation.

---

## 1. Demo Patient Accounts (10+ Authenticated Profiles)

All accounts can be logged into directly via `/login` with Role: **Patient**.
Default password for all demo patient accounts is: `password123`.

| # | Name | Email | Phone | Default Role | Notes / Demo State |
|---|------|-------|-------|--------------|--------------------|
| 1 | **Aarav Sharma** | `patient@qflow.com` | `+919999900001` | Patient | Token 1 (WAITING) in KEM Hospital General Medicine |
| 1b| **Aarav Sharma (Alt)** | `patient01@qflow.com` | `+919999900011` | Patient | Alias account for testing `patient01` |
| 2 | **Priya Patel** | `patient02@qflow.com` | `+919999900002` | Patient | Token 2 (WAITING) in KEM Hospital General Medicine |
| 3 | **Rohan Verma** | `patient03@qflow.com` | `+919999900003` | Patient | Token 3 (WAITING) in KEM Hospital General Medicine |
| 4 | **Ananya Iyer** | `patient04@qflow.com` | `+919999900004` | Patient | Token 4 (WAITING - Staff Phone Booking) |
| 5 | **Vikram Singh** | `patient05@qflow.com` | `+919999900005` | Patient | Token 5 (BOOKED - En route with Arrival Plan) |
| 6 | **Sneha Nair** | `patient06@qflow.com` | `+919999900006` | Patient | Available to book live during presentation |
| 7 | **Aditya Joshi** | `patient07@qflow.com` | `+919999900007` | Patient | Available to book live during presentation |
| 8 | **Meera Rao** | `patient08@qflow.com` | `+919999900008` | Patient | Available to book live during presentation |
| 9 | **Karan Malhotra** | `patient09@qflow.com` | `+919999900009` | Patient | Available to book live during presentation |
| 10| **Riya Sen** | `patient10@qflow.com` | `+919999900010` | Patient | Available to book live during presentation |

---

## 2. Hospital Staff Accounts (Strict Hospital Isolation)

All accounts can be logged into directly via `/login` with Role: **Staff**.
Default password for all staff accounts is: `password123`.

| Hospital Name | Staff Name | Staff Email | Phone | Assigned Hospital |
|---------------|------------|-------------|-------|-------------------|
| **King Edward Memorial (KEM) Hospital** | Sunil More | `staff.kem@qflow.com` | `+919820000001` | KEM Hospital, Parel |
| **BYL Nair Charitable Hospital** | Pooja Varma | `staff.nair@qflow.com` | `+919820000002` | Nair Hospital, Mumbai Central |
| **Lokmanya Tilak Municipal General Hospital (Sion)** | Rajesh Shinde | `staff.sion@qflow.com` | `+919820000003` | Sion Hospital, Sion |
| **Dr. R.N. Cooper Municipal General Hospital** | Amit Desai | `staff.cooper@qflow.com` | `+919820000004` | Cooper Hospital, Juhu |
| **Rajawadi Municipal General Hospital** | Girish Kadam | `staff.rajawadi@qflow.com` | `+919820000005` | Rajawadi Hospital, Ghatkopar |

---

## 3. Demo OPD Queue Reference (KEM General Medicine)

- **Hospital**: King Edward Memorial (KEM) Hospital
- **Department**: General Medicine
- **Doctor**: Dr. Arjun Mehta
- **Staff User**: Sunil More (`staff.kem@qflow.com`)
- **Queue Tokens Sequence**:
  - `Q001` (Aarav Sharma) - Arrived & Waiting
  - `Q002` (Priya Patel) - Arrived & Waiting
  - `Q003` (Rohan Verma) - Arrived & Waiting
  - `Q004` (Ananya Iyer) - Booked via Staff Phone
  - `Q005` (Vikram Singh) - Booked Online (En route)

During the demo presentation, log in as `staff.kem@qflow.com` to call `Q001`, start consultation, and complete consultation, and observe the live predictions and departure calculations update automatically on the patient screens without refreshing.
