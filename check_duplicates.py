import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT plate, zone_id, COUNT(*) as violation_count, array_agg(violation_id) as ids, array_agg(created_at) as timestamps
    FROM violations
    WHERE plate = 'NBY3978'
    GROUP BY plate, zone_id
""")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()