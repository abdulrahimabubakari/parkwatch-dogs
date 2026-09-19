import os
from datetime import datetime
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def check_plate(plate: str, zone_id: int, check_time: datetime = None):
    """
    Returns a dict describing whether this plate is validly parked in this zone
    right now. This is the core domain logic the whole system depends on.
    """
    if check_time is None:
        check_time = datetime.now()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM permits
        WHERE plate = %s AND zone_id = %s
        AND valid_from <= %s AND valid_to >= %s
    """, (plate, zone_id, check_time.date(), check_time.date()))
    permits = cur.fetchall()
    cur.close()
    conn.close()

    if not permits:
        return {"valid": False, "reason": "no_permit_for_zone"}

    current_day = DAY_NAMES[check_time.weekday()]
    current_hour = check_time.hour

    for permit in permits:
        allowed_days = permit["valid_days"].split(",")
        if current_day not in allowed_days:
            continue
        if not (permit["valid_start_hour"] <= current_hour < permit["valid_end_hour"]):
            continue
        # found a permit that's valid right now
        return {"valid": True, "reason": "valid_permit", "permit_id": permit["permit_id"]}

    # had a permit for this zone, but not valid at this day/hour
    return {"valid": False, "reason": "outside_permitted_hours"}


def log_violation(plate, zone_id, officer_id, violation_type, lat=None, lng=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO violations (plate, zone_id, officer_id, violation_type, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING violation_id, created_at
    """, (plate, zone_id, officer_id, violation_type, lat, lng))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"violation_id": result[0], "created_at": result[1].isoformat()}

def check_plate_and_log_violation(plate: str, zone_id: int, officer_id: str, check_time: datetime = None):
    """
    Atomic version: acquires a per-plate lock so two simultaneous requests
    for the SAME plate can't both create a violation. Requests for
    different plates are unaffected and still run fully in parallel.
    """
    if check_time is None:
        check_time = datetime.now()

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Lock scoped to this transaction, keyed on the plate string.
        # Any other transaction trying to lock the SAME plate will wait here
        # until this transaction commits or rolls back.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (plate,))

        cur.execute("""
            SELECT * FROM permits
            WHERE plate = %s AND zone_id = %s
            AND valid_from <= %s AND valid_to >= %s
        """, (plate, zone_id, check_time.date(), check_time.date()))
        permits = cur.fetchall()

        current_day = DAY_NAMES[check_time.weekday()]
        current_hour = check_time.hour

        valid_permit = None
        for permit in permits:
            allowed_days = permit["valid_days"].split(",")
            if current_day not in allowed_days:
                continue
            if not (permit["valid_start_hour"] <= current_hour < permit["valid_end_hour"]):
                continue
            valid_permit = permit
            break

        if valid_permit:
            conn.commit()
            return {"valid": True, "reason": "valid_permit", "permit_id": valid_permit["permit_id"]}

        reason = "no_permit_for_zone" if not permits else "outside_permitted_hours"

        # Inside the lock: check if a violation was JUST logged for this plate+zone.
        # If two requests race, the second one reaches this point only AFTER
        # the first has already committed its insert - so it will see it here.
        cur.execute("""
            SELECT violation_id, created_at FROM violations
            WHERE plate = %s AND zone_id = %s
            AND created_at > NOW() - INTERVAL '60 seconds'
            ORDER BY created_at DESC LIMIT 1
        """, (plate, zone_id))
        existing = cur.fetchone()

        if existing:
            conn.commit()
            return {
                "valid": False, "reason": reason, "duplicate": True,
                "violation_id": existing["violation_id"],
                "created_at": existing["created_at"].isoformat(),
            }

        cur.execute("""
            INSERT INTO violations (plate, zone_id, officer_id, violation_type)
            VALUES (%s, %s, %s, %s)
            RETURNING violation_id, created_at
        """, (plate, zone_id, officer_id, reason))
        result = cur.fetchone()
        conn.commit()

        return {
            "valid": False, "reason": reason, "duplicate": False,
            "violation_id": result["violation_id"],
            "created_at": result["created_at"].isoformat(),
        }
    finally:
        cur.close()
        conn.close()