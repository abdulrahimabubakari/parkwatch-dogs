# ParkWatch - Real-Time Campus Parking Enforcement System

A distributed, real-time system for flagging campus parking violations, built to replace manual permit checks with instant validation and live supervisor visibility - architected around WebSockets and Redis Pub/Sub rather than traditional request/response APIs.

**Live demo:** https://parkwatch-dogs.onrender.com/static/officer.html (officer view) and /static/supervisor.html (supervisor dashboard)

## The Problem

Campus parking enforcement is typically manual: an officer walks a lot, checks a plate against a paper list or a slow lookup, and writes up violations by hand. There's no live visibility into where officers are or what's been flagged until after the fact.

## Architecture

    Officer Client (WebSocket) --+
                                  +--> FastAPI Server A --+
    Supervisor Dashboard ---------+                       +--> Redis Pub/Sub --> broadcasts to ALL connected clients, across ALL server processes
                                  +--> FastAPI Server B --+
                                  |
                             PostgreSQL (permits, violations)

Officers hold a persistent WebSocket connection instead of polling an endpoint. When a plate is checked or a violation flagged, the event is published to a Redis channel; every connected client (regardless of which server process it's attached to) receives it instantly. This was deliberately verified by running two completely separate server processes during development and proving events crossed between them purely through Redis, not shared memory.

**Stack:** FastAPI, WebSockets, Redis (Upstash) Pub/Sub, PostgreSQL (Neon), vanilla JS frontend, deployed on Render.

## Key Engineering Problems Solved

### 1. Race condition on concurrent plate scans

Two officers scanning the same plate within milliseconds of each other could both independently create a violation record for one real event. Reproduced this reliably with a dedicated test script and confirmed via direct database query - duplicate violation IDs logged as little as 2ms apart.

**Fix:** a PostgreSQL advisory lock (pg_advisory_xact_lock) scoped per plate number. Concurrent requests for the same plate now execute sequentially and the second correctly detects the first's violation (duplicate: true); requests for different plates remain fully concurrent, unaffected.

### 2. Blocking database calls starving the event loop under concurrent load

A load test simulating 15 concurrent officers initially failed 15/15, all timing out. Root cause: the plate-check logic used synchronous psycopg2 calls directly inside an async WebSocket handler - one blocking database call froze the entire event loop, serializing every other connection instead of handling them concurrently.

**Fix:** moved the blocking database work onto a separate thread with asyncio.to_thread(), freeing the event loop to keep serving other connections while one check is in progress.

Before/after, 15 concurrent officers against the live deployment:

| | Before | After |
|---|---|---|
| Successful | 0/15 | 15/15 |
| Failures | 15/15 (timeout) | 0/15 |
| Avg response time | N/A (all timed out) | 5.87s |

### 3. Dead connections to hosted Redis

A long-lived Redis client silently failed after Upstash closed an idle connection, causing every subsequent publish to fail with no visible error. Fixed with health_check_interval, socket_keepalive, and an automatic one-time retry on publish failure.

### 4. Foreign key violation from database ID drift across reseeds

Running db_setup.py multiple times during development caused zone IDs to drift upward (DELETE does not reset PostgreSQL's auto-increment sequence). A stale "zone 1" reference in test data no longer matched any real zone, causing every check against it to fail at the violation-insert step with a ForeignKeyViolation - which threw an unhandled exception mid-request and eventually closed the WebSocket connection, making the failure look like a connection bug rather than a data bug.

Diagnosed directly from Render's live logs by tracing the exact exception and confirming the mismatch with a direct database query, rather than guessing from symptoms alone.

**Fix:** changed db_setup.py to use TRUNCATE TABLE ... RESTART IDENTITY CASCADE instead of separate DELETE statements, so every reseed reliably resets to the same starting IDs.

## Known Limitations (Honest Ones)

- **No connection pooling** - every database call opens a fresh connection. The next real optimization would be a connection pool (e.g. psycopg2.pool or moving to an async driver like asyncpg), which would likely cut response times substantially under load.
- **Redis Pub/Sub has no replay** - a supervisor dashboard only sees events published while it's connected; there's no history for a client that connects late. A production version would likely persist events to Postgres as the source of truth and use Pub/Sub purely for live delivery.
- **Render free tier constraints** - the ~5.9s average response time under load reflects a shared, limited-CPU free-tier instance, not the architecture itself; the 0-failure result is the meaningful proof point, not the raw speed.
- **Synthetic data only** - permits and violations are generated test data, not a real institutional dataset.

## Running It Locally

    git clone https://github.com/abdulrahimabubakari/parkwatch-dogs.git
    cd parkwatch-dogs
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

Create a .env file with:

    REDIS_URL=rediss://your-upstash-url
    DATABASE_URL=your-neon-postgres-url

Seed the database:

    python db_setup.py

Run it:

    uvicorn api.main:app --reload

Open http://127.0.0.1:8000/static/officer.html and http://127.0.0.1:8000/static/supervisor.html.

## Development Process

Built over 7 days with deliberate emphasis on proving each piece works before building on top of it - every major feature was verified with a dedicated test script and, where a bug was found, reproduced with evidence before being fixed. Developed using feature branches and pull requests for each day's work rather than committing directly to main; see the closed PRs in this repo for the full history of what changed and why.