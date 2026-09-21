import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT zone_id, name FROM zones ORDER BY zone_id")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()