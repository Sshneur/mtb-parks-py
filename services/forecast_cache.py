import json
from datetime import datetime, timedelta, timezone
from database.connection import get_connection

CACHE_TTL = timedelta(hours=1)

def get_cached_forecast(park_id: str, max_age=CACHE_TTL):
    """Return cached forecast dict if fresh enough, else None. max_age=None — любой возраст."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT forecast_data, fetched_at FROM soil_forecast_cache WHERE park_id = ?",
            (park_id,)
        ).fetchone()
        if not row:
            return None
        fetched = datetime.fromisoformat(row["fetched_at"])
        if max_age is not None and datetime.now(timezone.utc) - fetched > max_age:
            return None
        return json.loads(row["forecast_data"])
    finally:
        conn.close()

def set_cached_forecast(park_id: str, forecast_data: dict):
    """Store forecast in cache (upsert)."""
    conn = get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR REPLACE INTO soil_forecast_cache (park_id, forecast_data, fetched_at)
               VALUES (?, ?, ?)""",
            (park_id, json.dumps(forecast_data, ensure_ascii=False), now)
        )
        conn.commit()
    finally:
        conn.close()
