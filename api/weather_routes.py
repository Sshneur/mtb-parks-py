from fastapi import APIRouter
from config.parks import PARKS, SOIL_COEFFICIENTS, FOREST_COEFFICIENT, RAIN_HISTORY_HOURS
from services import open_meteo
from datetime import datetime, timedelta, timezone

router = APIRouter()

def get_soil_status(rain_total: float, dry_hours: float, hours_since_rain: float = None, is_asphalt: bool = False) -> str:
    """Статусы: Болото 🌿 → Мокро 💧 → Альденте 🌵 → Сухо ✅ → Бетон 🪨"""
    
    if hours_since_rain is not None and hours_since_rain >= 144:
        return "Бетон 🪨"
    if dry_hours >= 72:
        return "Болото 🌿"
    if dry_hours > 0 and dry_hours < 72:
        return "Мокро 💧"
    if is_asphalt and dry_hours == 0:
        return "Сухо ✅"
    if dry_hours == 0 and rain_total > 0.5:
        return "Альденте 🌵"
    if dry_hours == 0 and rain_total <= 0.5:
        return "Сухо ✅"
    return "Сухо ✅"


def calculate_soil_moisture(history_data: dict, forecast_data: dict, soil_type: str, forest_coef: float) -> dict:
    """Баланс влаги: история + прогноз на сегодня."""
    now = datetime.now(timezone.utc)
    soil = SOIL_COEFFICIENTS.get(soil_type, SOIL_COEFFICIENTS["loam"])
    k_t = soil["k_t"]
    k_w = soil["k_w"]
    k_s = soil["k_s"]
    forest_factor = forest_coef

    hourly_data = []
    
    # 1. Исторические данные
    if history_data and history_data.get("hourly"):
        h = history_data["hourly"]
        times = h.get("time", [])
        rains = h.get("rain", [])
        for i, t_str in enumerate(times):
            t = None
            for fmt in [lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                        lambda s: datetime.fromisoformat(s)]:
                try:
                    t = fmt(t_str)
                    break
                except:
                    continue
            
            if t is None:
                continue
            
            # ГАРАНТИРУЕМ часовой пояс
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            
            rain = rains[i] or 0
            hourly_data.append({"time": t, "rain": rain, "temp": 15, "wind": 5})

    # 2. Прогноз на сегодня
    if forecast_data and forecast_data.get("daily"):
        daily = forecast_data["daily"]
        daily_times = daily.get("time", [])
        daily_rains = daily.get("rain_sum", [])
        for i, d_str in enumerate(daily_times):
            try:
                d = datetime.fromisoformat(d_str)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
            except:
                continue
            rain = daily_rains[i] or 0
            if rain > 0:
                hourly_rain = rain / 8
                for h in range(12, 20):
                    hour_time = d.replace(hour=h, minute=0, second=0, tzinfo=timezone.utc)
                    hourly_data.append({"time": hour_time, "rain": hourly_rain, "temp": 15, "wind": 5})

    # Сортируем
    hourly_data.sort(key=lambda x: x["time"])

    # Моделируем баланс
    W = 0.0
    W_max = 1.0
    last_rain_time = None
    total_rain = 0

    for hour in hourly_data:
        f_T = 0.05 * max(hour["temp"], 0)
        g_v = 0.03 * hour["wind"]
        denominator = forest_factor * (k_t * f_T + k_w * g_v + k_s)
        evaporation_per_hour = denominator

        W = max(0, W - evaporation_per_hour)

        if hour["rain"] > 0:
            W = min(W_max, W + hour["rain"] / 10)
            total_rain += hour["rain"]
            last_rain_time = hour["time"]

    # Текущая скорость испарения
    temp = forecast_data["current"]["temperature_2m"] if forecast_data and forecast_data.get("current") else 15
    wind = forecast_data["current"]["wind_speed_10m"] if forecast_data and forecast_data.get("current") else 0
    f_T = 0.05 * max(temp, 0)
    g_v = 0.03 * wind
    denominator = forest_factor * (k_t * f_T + k_w * g_v + k_s)
    current_evaporation_per_hour = denominator

    if W > 0 and current_evaporation_per_hour > 0:
        dry_hours = W / current_evaporation_per_hour
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
        "last_rain_time": last_rain_time,
        "hours_since_rain": hours_since_rain
    }


@router.get("/api/groups")
async def get_groups():
    return [{"id": gid, "name": PARKS[gid]["name"]} for gid in PARKS]


@router.get("/api/weather/{group_id}")
async def get_weather(group_id: str = "mtb_parks"):
    if group_id not in PARKS:
        return {"error": "Группа не найдена"}

    parks = PARKS[group_id]["parks"]
    results = []

    for park in parks:
        try:
            print(f"Запрос для {park['name']}...")
            forecast = await open_meteo.get_forecast(park["lat"], park["lon"])
            history = await open_meteo.get_history(park["lat"], park["lon"])

            soil_type = park.get("soil", "loam")
            forest_coef = park.get("forest_coef", FOREST_COEFFICIENT)

            moisture = calculate_soil_moisture(history, forecast, soil_type, forest_coef)
            dry_time_hours = moisture["dry_hours"]
            rain_total = moisture["total_rain"]
            last_rain_time = moisture["last_rain_time"]
            hours_since_rain = moisture["hours_since_rain"]
            now = datetime.now(timezone.utc)

            if dry_time_hours > 0 and last_rain_time:
                try:
                    if last_rain_time.tzinfo is None:
                        last_rain_time = last_rain_time.replace(tzinfo=timezone.utc)
                    dry_target = last_rain_time + timedelta(hours=dry_time_hours)
                    if dry_target < now:
                        dry_time_hours = 0
                        dry_target = now
                    else:
                        hours_passed = (now - last_rain_time).total_seconds() / 3600
                        remaining = max(0, dry_time_hours - hours_passed)
                        dry_target = now + timedelta(hours=remaining)
                except Exception as e:
                    print(f"Ошибка dry_target для {park['name']}: {e}")
                    dry_target = now + timedelta(hours=dry_time_hours)
            elif dry_time_hours > 0:
                dry_target = now + timedelta(hours=dry_time_hours)
            else:
                dry_time_hours = 0
                dry_target = now

            is_asphalt = soil_type == "asphalt"
            soil_status = get_soil_status(rain_total, dry_time_hours, hours_since_rain, is_asphalt)

            results.append({
                "park": {
                    "id": park["id"],
                    "name": park["name"],
                    "lat": park["lat"],
                    "lon": park["lon"],
                    "dryHours": round(dry_time_hours, 1),
                    "startDate": park.get("start_date"),
                    "soil": soil_type,
                    "forest": park.get("forest", True),
                    "forest_coef": forest_coef,
                    "rain_6d": round(rain_total, 1),
                    "rain_forecast": 0,
                    "rain_total": round(rain_total, 1),
                    "current_moisture": moisture["current_moisture"],
                    "soilStatus": soil_status,
                    "dryTarget": dry_target.isoformat()
                },
                "forecast": forecast,
                "history": history,
                "provider": "openmeteo",
                "error": None
            })
        except Exception as e:
            print(f"Ошибка для {park['name']}: {e}")
            results.append({
                "park": {
                    "id": park["id"],
                    "name": park["name"],
                    "lat": park["lat"],
                    "lon": park["lon"],
                    "dryHours": park["dry_hours"],
                    "startDate": park.get("start_date"),
                    "soil": soil_type,
                    "forest": park.get("forest", True),
                    "forest_coef": forest_coef,
                    "rain_6d": 0,
                    "rain_forecast": 0,
                    "rain_total": 0,
                    "current_moisture": 0,
                    "soilStatus": "Нет данных",
                    "dryTarget": None
                },
                "forecast": None,
                "history": None,
                "provider": "openmeteo",
                "error": str(e)
            })

    return results