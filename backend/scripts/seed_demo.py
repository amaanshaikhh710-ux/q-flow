"""Idempotent seed script for Q-FLOW demo data.

Ensures that:
- 5 municipal hospitals exist
- 15 departments exist
- 15 doctors exist with 15-day availability schedules
- Staff accounts for all 5 hospitals exist
- 10 demo patient accounts from LoginPage.tsx exist
- Admin user exists
- Real live queues and sample entries are initialized
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.seed_service import seed_demo_data


def seed():
    print("=== Running Idempotent Q-FLOW Demo Seeding ===")
    with SessionLocal() as db:
        counts = seed_demo_data(db)
        print("=== Demo Seeding Summary ===")
        print(f"  Hospitals:   {counts['hospitals']}")
        print(f"  Departments: {counts['departments']}")
        print(f"  Doctors:     {counts['doctors']}")
        print(f"  Schedules:   {counts['schedules']}")
        print(f"  Users:       {counts['users']}")
        print("============================\n")


if __name__ == "__main__":
    seed()
