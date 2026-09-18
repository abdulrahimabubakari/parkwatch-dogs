import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("SELECT plate, zone_id, valid_to FROM permits WHERE valid_to < CURRENT_DATE LIMIT 1")
expired = cur.fetchone()
print("Expired permit example:", expired)

cur.execute("SELECT plate, zone_id, valid_start_hour, valid_end_hour, valid_days FROM permits WHERE valid_start_hour > 0 LIMIT 1")
time_restricted = cur.fetchone()
print("Time-restricted permit example:", time_restricted)

cur.execute("SELECT plate, zone_id FROM permits WHERE valid_to > CURRENT_DATE AND valid_start_hour = 0 LIMIT 1")
normal = cur.fetchone()
print("Normal valid permit example:", normal)

cur.close()
conn.close()