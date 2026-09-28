import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("=== HOSPITALS IN DB ===")
    res = conn.execute(text("SELECT id, name, address, latitude, longitude FROM hospitals")).fetchall()
    for row in res:
        print(f"{row[0]} | {row[1]} | {row[2]}")
    print(f"Total hospitals: {len(res)}")
    
    print("\n=== DOCTORS IN DB ===")
    docs = conn.execute(text("SELECT id, name, department_id FROM doctors LIMIT 15")).fetchall()
    for d in docs:
        print(f"{d[0]} | {d[1]}")
    doc_count = conn.execute(text("SELECT count(*) FROM doctors")).scalar()
    print(f"Total doctors: {doc_count}")
    
    print("\n=== QUEUES IN DB ===")
    q_count = conn.execute(text("SELECT count(*) FROM queues")).scalar()
    print(f"Total queues: {q_count}")

    print("\n=== STAFF USERS IN DB ===")
    staff = conn.execute(text("SELECT id, email, role, hospital_id FROM users WHERE lower(role) = 'staff'")).fetchall()
    for s in staff:
        print(f"{s[0]} | {s[1]} | {s[3]}")

    print("\n=== PATIENT USERS IN DB ===")
    patients = conn.execute(text("SELECT id, email, role, name FROM users WHERE lower(role) = 'patient'")).fetchall()
    for p in patients:
        print(f"{p[0]} | {p[1]} | {p[3]}")
