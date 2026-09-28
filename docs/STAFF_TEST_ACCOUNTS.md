# Q-FLOW Development & Demo Staff Accounts

This document lists the **5 distinct development and demo staff test accounts** provisioned for Q-FLOW.
Each account is assigned to a unique, realistic public hospital in Mumbai to verify and demonstrate hospital-scoped role-based access control and strict data isolation.

> [!IMPORTANT]
> **Hospital-Scoped Authorization Rules:**
> - Staff members can **only** view, manage, and mutate queues and appointments for their assigned hospital.
> - Attempting to view or mutate another hospital's queues results in an immediate **`403 Forbidden`** response.
> - Staff accounts are pre-provisioned. Public staff self-registration is strictly disabled.
> - There is NO "Public View OPD" in the staff portal. Staff see ONLY their assigned hospital.

---

## 1. Demo Staff Accounts (5 Distinct Hospitals)

| # | Email Address | Password | Role | Assigned Hospital | Purpose / Department Scope |
|---|---------------|----------|------|-------------------|-----------------------------|
| **1** | `staff.kem@qflow.com` | `password123` | `staff` | **King Edward Memorial (KEM) Hospital** (Parel) | Central Reception & OPD Desk |
| **2** | `staff.nair@qflow.com` | `password123` | `staff` | **BYL Nair Charitable Hospital** (Mumbai Central) | OPD Queue Desk |
| **3** | `staff.sion@qflow.com` | `password123` | `staff` | **Lokmanya Tilak Municipal General Hospital** (Sion) | Trauma & OPD Coordination |
| **4** | `staff.jj@qflow.com` | `password123` | `staff` | **Sir J.J. Group of Hospitals** (Byculla) | Operations & Scheduling Staff |
| **5** | `staff.rajawadi@qflow.com` | `password123` | `staff` | **Rajawadi Municipal General Hospital** (Ghatkopar) | Front Desk & Walk-in Intake |

---

## 2. Test Scenarios & Verification Matrix

| Test Scenario | Acting Account | Target Queue / Hospital | Expected Result |
|---|---|---|---|
| **Intra-Hospital Booking** | `staff.kem@qflow.com` | KEM Hospital Queue | **`201 Created`** — Phone/Walk-in booked into unified queue |
| **Intra-Hospital Arrival Control** | `staff.kem@qflow.com` | KEM Hospital Queue Entry | **`200 OK`** — Status moves `BOOKED -> ARRIVED` |
| **Intra-Hospital Consultation Control** | `staff.kem@qflow.com` | KEM Hospital Queue Entry | **`200 OK`** — Consultation started/ended, duration recorded |
| **Cross-Hospital Access Denial** | `staff.kem@qflow.com` | BYL Nair Hospital Queue | **`403 Forbidden`** — Cross-hospital access strictly denied |
| **Cross-Hospital Mutation Denial** | `staff.nair@qflow.com` | Sion Hospital Queue | **`403 Forbidden`** — Cross-hospital mutation strictly denied |
| **Cross-Hospital Emergency Denial** | `staff.jj@qflow.com` | Rajawadi Hospital Queue | **`403 Forbidden`** — Cross-hospital emergency event denied |

---

## 3. Patient Test Account Reference

For end-to-end multi-party testing:

| Email | Password | Role | Usage |
|---|---|---|---|
| `patient@qflow.com` | `password123` | `patient` | General online patient booking, tracking, and travel ETA |

> Note: New patients can also self-register freely at `/register`. Self-registration strictly provisions `patient` role accounts.
