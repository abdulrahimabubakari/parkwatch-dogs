import os
import random
from datetime import datetime, timedelta
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# --- Schema ---
cur.execute("""
    CREATE TABLE IF NOT EXISTS zones (
        zone_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS permits (
        permit_id SERIAL PRIMARY KEY,
        plate TEXT NOT NULL,
        zone_id INTEGER REFERENCES zones(zone_id),
        valid_from DATE NOT NULL,
        valid_to DATE NOT NULL,
        valid_start_hour INTEGER NOT NULL DEFAULT 0,
        valid_end_hour INTEGER NOT NULL DEFAULT 24,
        valid_days TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS violations (
        violation_id SERIAL PRIMARY KEY,
        plate TEXT NOT NULL,
        zone_id INTEGER REFERENCES zones(zone_id),
        officer_id TEXT NOT NULL,
        violation_type TEXT NOT NULL,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

conn.commit()
print("Schema created.")

# --- Seed zones ---
zone_names = ["Lot A - Main Campus", "Lot B - Residence Halls", "Lot C - Athletics", "Lot D - Visitor", "Lot E - Faculty"]
cur.execute("TRUNCATE TABLE violations, permits, zones RESTART IDENTITY CASCADE")
conn.commit()

zone_ids = []
for name in zone_names:
    cur.execute("INSERT INTO zones (name) VALUES (%s) RETURNING zone_id", (name,))
    zone_ids.append(cur.fetchone()[0])
conn.commit()
print(f"Seeded {len(zone_ids)} zones.")

# --- Seed permits, with intentional edge cases ---
today = datetime.now().date()

def random_plate():
    letters = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=3))
    numbers = "".join(random.choices("0123456789", k=4))
    return f"{letters}{numbers}"

permits_data = []

# 60 "normal" valid permits, full day access, valid for the next 6 months
for _ in range(60):
    permits_data.append({
        "plate": random_plate(),
        "zone_id": random.choice(zone_ids),
        "valid_from": today - timedelta(days=30),
        "valid_to": today + timedelta(days=180),
        "valid_start_hour": 0,
        "valid_end_hour": 24,
        "valid_days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
    })

# 15 EXPIRED permits (valid_to in the past) - edge case
for _ in range(15):
    permits_data.append({
        "plate": random_plate(),
        "zone_id": random.choice(zone_ids),
        "valid_from": today - timedelta(days=200),
        "valid_to": today - timedelta(days=10),
        "valid_start_hour": 0,
        "valid_end_hour": 24,
        "valid_days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
    })

# 15 TIME-RESTRICTED permits (only valid weekdays 8am-6pm) - edge case
for _ in range(15):
    permits_data.append({
        "plate": random_plate(),
        "zone_id": random.choice(zone_ids),
        "valid_from": today - timedelta(days=30),
        "valid_to": today + timedelta(days=180),
        "valid_start_hour": 8,
        "valid_end_hour": 18,
        "valid_days": "Mon,Tue,Wed,Thu,Fri",
    })

for p in permits_data:
    cur.execute("""
        INSERT INTO permits (plate, zone_id, valid_from, valid_to, valid_start_hour, valid_end_hour, valid_days)
        VALUES (%(plate)s, %(zone_id)s, %(valid_from)s, %(valid_to)s, %(valid_start_hour)s, %(valid_end_hour)s, %(valid_days)s)
    """, p)

conn.commit()
print(f"Seeded {len(permits_data)} permits ({60} normal, {15} expired, {15} time-restricted).")

cur.close()
conn.close()
print("Done.")