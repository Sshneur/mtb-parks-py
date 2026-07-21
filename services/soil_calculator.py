from datetime import datetime, timezone
from database.models import SOIL_COEFFICIENTS
from api.utils import MOSCOW_TZ


def get_soil_status(rain_total: float, dry_hours: float, hours_since_rain: float = None, is_asphalt: bool = False) -> str:
    if hours_since_rain is not None and hours_since_rain >= 144:
        return "Бетон 🪨"
    if dry_hours >= 72:
        return "Болото 🟤"
    if dry_hours > 24:
        return "Мокро 💧"
    if dry_hours > 0:
        return "Альденте 🌵"
    if is_asphalt and dry_hours <= 0:
        return "Сухо ✅"
    return "Сухо ✅"


def calculate_soil_moisture_from_db(park: dict, hourly_data: list) -> dict:
    now = datetime.now(timezone.utc)
    soil = SOIL_COEFFICIENTS.get(park.get("soil_type", "loam"), SOIL_COEFFICIENTS["loam"])
    k_t = soil["k_t"]
    k_w = soil["k_w"]
    k_r = soil["k_r"]
    k_s = soil["k_s"]
    forest_factor = park.get("forest_coef", 0.3)

    W = 0.0
    W_max = 1.0
    last_rain_time = None
    total_rain = 0.0

    for hour in hourly_data:
        timestamp = hour["timestamp"]
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except:
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except:
                    continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        temp = hour.get("temperature") or 15
        wind = hour.get("wind_speed") or 0
        rad = hour.get("radiation") or 0
        rain = hour.get("rain") or 0

        if rain > 0:
            W = min(W_max, W + rain / 10)
            total_rain += rain
            last_rain_time = timestamp
        else:
            f_T = 0.05 * max(temp, 0)
            g_v = 0.03 * wind
            g_r = 0.001 * rad
            evaporation = forest_factor * (k_t * f_T + k_w * g_v + k_r * g_r + k_s)
            W = max(0.0, W - evaporation)

    # Текущая скорость испарения (по последнему часу без дождя)
    last_temp, last_wind, last_rad = 15, 0, 0
    for h in reversed(hourly_data):
        if (h.get("rain") or 0) == 0:
            last_temp = h.get("temperature") or 15
            last_wind = h.get("wind_speed") or 0
            last_rad = h.get("radiation") or 0
            break

    f_T = 0.05 * max(last_temp, 0)
    g_v = 0.03 * last_wind
    g_r = 0.001 * last_rad
    current_evaporation = forest_factor * (k_t * f_T + k_w * g_v + k_r * g_r + k_s)

    if W > 0 and current_evaporation > 0:
        dry_hours = W / current_evaporation
    else:
        dry_hours = 0

    hours_since_rain = None
    if last_rain_time:
        try:
            hours_since_rain = (now - last_rain_time).total_seconds() / 3600
        except:
            pass

    return {
        "current_moisture": round(W, 3),
        "dry_hours": round(dry_hours, 1),
        "total_rain": round(total_rain, 1),
        "last_rain_time": last_rain_time.isoformat() if last_rain_time else None,
        "hours_since_rain": round(hours_since_rain, 1) if hours_since_rain else None,
        "evaporation_rate": round(current_evaporation, 4),
    }


def calculate_green_days(park: dict, hourly_data: list, month_str: str) -> list:
    soil = SOIL_COEFFICIENTS.get(park.get("soil_type", "loam"), SOIL_COEFFICIENTS["loam"])
    k_t, k_w, k_r, k_s = soil["k_t"], soil["k_w"], soil["k_r"], soil["k_s"]
    forest_factor = park.get("forest_coef", 0.3)

    W = 0.0
    W_max = 1.0
    daily_results = {}

    for hour in hourly_data:
        timestamp = hour["timestamp"]
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except:
                continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        tz_msk = timestamp.astimezone(MOSCOW_TZ)
        day_key = tz_msk.strftime("%Y-%m-%d")

        temp = hour.get("temperature") or 15
        wind = hour.get("wind_speed") or 0
        rad = hour.get("radiation") or 0
        rain = hour.get("rain") or 0

        if rain > 0:
            W = min(W_max, W + rain / 10)
        else:
            f_T = 0.05 * max(temp, 0)
            g_v = 0.03 * wind
            g_r = 0.001 * rad
            evaporation = forest_factor * (k_t * f_T + k_w * g_v + k_r * g_r + k_s)
            W = max(0.0, W - evaporation)

        daily_results[day_key] = round(W, 3)

    import calendar as _cal
    year, month = map(int, month_str.split("-"))
    _, last_day = _cal.monthrange(year, month)

    result = []
    for day in range(1, last_day + 1):
        day_key = f"{month_str}-{day:02d}"
        W_val = daily_results.get(day_key)

        if W_val is None:
            status = "no_data"
            label = "Нет данных"
        elif W_val == 0:
            status = "dry"
            label = "Сухо"
        elif W_val < 0.3:
            status = "wet"
            label = "Мокро"
        else:
            status = "bog"
            label = "Болото"

        result.append({
            "date": day_key,
            "W": W_val,
            "status": status,
            "label": label,
        })

    return result