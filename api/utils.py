from datetime import datetime, timedelta, timezone

MOSCOW_TZ = timezone(timedelta(hours=3))


def parse_time(t) -> datetime:
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_msk(t) -> str:
    dt = parse_time(t)
    msk = dt.astimezone(MOSCOW_TZ)
    return msk.strftime("%Y-%m-%dT%H:%M+03:00")


def weather_code(temp: float, rain: float) -> int:
    if rain and rain > 2:
        return 63
    elif rain and rain > 0.5:
        return 61
    elif rain and rain > 0:
        return 80
    elif temp is not None and temp > 25:
        return 1
    elif temp is not None and temp > 15:
        return 2
    else:
        return 3


def get_reset_time_msk():
    now_msk = datetime.now(timezone.utc) + timedelta(hours=3)
    if now_msk.hour >= 4:
        reset_msk = now_msk.replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        reset_msk = (now_msk - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    reset_utc = reset_msk - timedelta(hours=3)
    return reset_utc


def build_forecast(forecast_data: list, hour_start: datetime, daily_data: dict = None) -> dict:
    future_hours = []
    for h in forecast_data:
        t = parse_time(h["timestamp"])
        if t >= hour_start:
            future_hours.append(h)
        if len(future_hours) >= 6:
            break

    if len(future_hours) < 6:
        future_hours = forecast_data[-6:] if forecast_data else []

    hourly_forecast = {
        "time": [to_msk(h["timestamp"]) for h in future_hours],
        "temperature_2m": [h.get("temperature") or 15 for h in future_hours],
        "rain": [h.get("rain") or 0 for h in future_hours],
        "weather_code": [
            weather_code(h.get("temperature"), h.get("rain"))
            for h in future_hours
        ]
    }

    if daily_data and "daily" in daily_data:
        daily_forecast = daily_data["daily"]
    else:
        daily_forecast = {
            "time": [],
            "temperature_2m_max": [],
            "rain_sum": [],
            "weather_code": []
        }

    return {"hourly": hourly_forecast, "daily": daily_forecast}


def build_daily_from_db(conn, park_id: str) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    rows = conn.execute(
        "SELECT date, temperature_max, rain_sum, weather_code FROM weather_daily WHERE park_id = ? AND date >= ? ORDER BY date ASC",
        (park_id, today)
    ).fetchall()
    return {
        "time": [r["date"] for r in rows],
        "temperature_2m_max": [r["temperature_max"] for r in rows],
        "rain_sum": [r["rain_sum"] or 0 for r in rows],
        "weather_code": [r["weather_code"] for r in rows],
    }


def get_park_vote_stats(conn, park_id: str, reset_time_utc) -> dict:
    reset_time_str = reset_time_utc.strftime("%Y-%m-%d %H:%M:%S")
    rain_period_start = (reset_time_utc - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    rain_rows = conn.execute("""
        SELECT COUNT(*) as cnt FROM weather_hourly
        WHERE park_id = ? AND rain > 0
          AND datetime(timestamp) >= datetime(?) AND datetime(timestamp) < datetime(?)
    """, (park_id, rain_period_start, reset_time_str)).fetchone()

    rain_reset = False
    avg = None
    count = 0

    if rain_rows and rain_rows["cnt"] > 0:
        rain_reset = True
        row = conn.execute("""
            SELECT AVG(vote) as avg, COUNT(*) as cnt
            FROM park_photos
            WHERE park_id = ? AND status = 'approved' AND datetime(created_at) > datetime(?)
        """, (park_id, reset_time_str)).fetchone()
        if row and row["cnt"] > 0:
            avg = round(row["avg"], 2)
            count = row["cnt"]
        else:
            avg = None
            count = 0
    else:
        row = conn.execute("""
            SELECT AVG(vote) as avg, COUNT(*) as cnt
            FROM park_photos
            WHERE park_id = ? AND status = 'approved'
        """, (park_id,)).fetchone()
        avg = round(row["avg"], 2) if row["avg"] is not None else None
        count = row["cnt"] or 0

    return {"avg": avg, "count": count, "rain_reset": rain_reset}
