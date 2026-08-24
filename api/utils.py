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
