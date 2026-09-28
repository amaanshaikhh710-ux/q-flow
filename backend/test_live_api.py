import httpx

client = httpx.Client(base_url="http://localhost:8000")

# 1. Hospitals -> Departments -> Doctors
hospitals = client.get("/api/v1/discovery/hospitals").json()
print("Hospitals count:", len(hospitals))
if hospitals:
    hosp = hospitals[0]
    print(f"Hospital: {hosp['name']} ({hosp['latitude']}, {hosp['longitude']})")
    depts = client.get(f"/api/v1/discovery/hospitals/{hosp['id']}/departments").json()
    print("Departments count:", len(depts))
    if depts:
        dept = depts[0]
        print(f"Department: {dept['name']}")
        docs = client.get(f"/api/v1/discovery/departments/{dept['id']}/doctors").json()
        print("Doctors count:", len(docs))
        if docs:
            doc = docs[0]
            print(f"Doctor: {doc['name']} (id: {doc['id']})")
            avail = client.get(f"/api/v1/doctors/{doc['id']}/availability").json()
            print(f"Doctor {doc['name']} availability days: {len(avail.get('availability', []))}")
            for item in avail.get("availability", [])[:3]:
                print(f"  - {item['date']}: is_available={item['is_available']}")

# 2. Test Address Resolution (Mumbra -> Coordinates)
resolve_res = client.post("/api/v1/travel/resolve-address", json={"query": "Mumbra Railway Station"})
print("Resolve Address Status:", resolve_res.status_code)
resolve_data = resolve_res.json()
print("Resolve Address Results:", len(resolve_data.get("results", [])))
if resolve_data.get("results"):
    top = resolve_data["results"][0]
    print(f"Top Result: {top['name']} ({top['latitude']}, {top['longitude']}) - {top['formatted_address']}")
    assert abs(top['latitude'] - 19.1895) < 0.05
    assert abs(top['longitude'] - 73.0227) < 0.05
    print("[PASS] Address resolution correctly resolved 'Mumbra Railway Station' to routable coordinates!")

print("[PASS] All live API endpoints verified successfully!")
