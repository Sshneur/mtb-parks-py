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
    # Для асфальта: таймер кончился → сразу Сухо
    if is_asphalt and dry_hours == 0:
        return "Сухо ✅"
    # Для грунта: таймер кончился, осадки были → Альденте
    if dry_hours == 0 and rain_total > 0.5:
        return "Альденте 🌵"
    if dry_hours == 0 and rain_total <= 0.5:
        return "Сухо ✅"
    return "Сухо ✅"

def calc_dry_time(soil_type: str, temperature: float, wind_speed: float, rain_total: float, forest_coef: float = FOREST_COEFFICIENT) -> float:
    if rain_total <= 0.5:
        return 0

    soil = SOIL_COEFFICIENTS.get(soil_type, SOIL_COEFFICIENTS["loam"])
    W0 = soil["W0"]
    We = 0
    k_t = soil["k_t"]
    k_w = soil["k_w"]
    k_s = soil["k_s"]

    f_T = 0.05 * max(temperature, 0)
    g_v = 0.03 * wind_speed

    forest_factor = forest_coef

    denominator = forest_factor * (k_t * f_T + k_w * g_v + k_s)
    if denominator <= 0:
        return 999

    T_base = (W0 - We) / denominator
    saturation_factor = 1 + rain_total / 20
    T = T_base * saturation_factor
    return round(T, 1)


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

            rain_history = 0
            rain_forecast = 0
            last_rain_time = None
            now = datetime.now(timezone.utc)
            hours_since_rain = None

            if history and history.get("hourly"):
                h = history["hourly"]
                times = h.get("time", [])
                rains = h.get("rain", [])
                for i, t_str in enumerate(times):
                    rain = rains[i] or 0
                    rain_history += rain
                    if rain > 0:
                        try:
                            t = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                            if last_rain_time is None or t > last_rain_time:
                                last_rain_time = t
                        except:
                            try:
                                t = datetime.fromisoformat(t_str)
                                if t.tzinfo is None:
                                    t = t.replace(tzinfo=timezone.utc)
                                if last_rain_time is None or t > last_rain_time:
                                    last_rain_time = t
                            except:
                                pass

            if forecast and forecast.get("daily"):
                daily = forecast["daily"]
                daily_rains = daily.get("rain_sum", [])
                daily_times = daily.get("time", [])
                
                consecutive_rain_started = False
                
                if last_rain_time:
                    try:
                        hours_since_last = (now - last_rain_time).total_seconds() / 3600
                        if hours_since_last <= 24:
                            consecutive_rain_started = True
                    except:
                        pass
                
                for i, r in enumerate(daily_rains):
                    if r > 0.5:
                        try:
                            forecast_rain_time = datetime.fromisoformat(daily_times[i]).replace(tzinfo=timezone.utc) + timedelta(hours=23, minutes=59)
                            
                            if consecutive_rain_started or i == 0:
                                rain_forecast += r
                                if last_rain_time is None or forecast_rain_time > last_rain_time:
                                    last_rain_time = forecast_rain_time
                                consecutive_rain_started = True
                            elif i > 0 and daily_rains[i-1] > 0.5:
                                rain_forecast += r
                                if last_rain_time is None or forecast_rain_time > last_rain_time:
                                    last_rain_time = forecast_rain_time
                                consecutive_rain_started = True
                            else:
                                break
                        except:
                            pass

            rain_total = rain_history + rain_forecast

            if last_rain_time:
                try:
                    if last_rain_time.tzinfo is None:
                        last_rain_time = last_rain_time.replace(tzinfo=timezone.utc)
                    diff = now - last_rain_time
                    hours_since_rain = diff.total_seconds() / 3600
                    if hours_since_rain < 0:
                        hours_since_rain = 0
                except Exception as e:
                    print(f"Ошибка hours_since_rain: {e}")
                    hours_since_rain = None

            temp = forecast["current"]["temperature_2m"] if forecast and forecast.get("current") else 15
            wind = forecast["current"]["wind_speed_10m"] if forecast and forecast.get("current") else 0

            dry_time_hours = calc_dry_time(
                park.get("soil", "loam"),
                temp,
                wind,
                rain_total,
                park.get("forest_coef", FOREST_COEFFICIENT)
            )

            if dry_time_hours > 0 and last_rain_time:
                try:
                    if last_rain_time.tzinfo is None:
                        last_rain_time = last_rain_time.replace(tzinfo=timezone.utc)
                    dry_target = last_rain_time + timedelta(hours=dry_time_hours)
                    # Если уже просохло — сбрасываем таймер
                    if dry_target < now:
                        dry_time_hours = 0
                        dry_target = now
                    else:
                        # Вычитаем прошедшее время
                        hours_passed = (now - last_rain_time).total_seconds() / 3600
                        remaining = max(0, dry_time_hours - hours_passed)
                        dry_target = now + timedelta(hours=remaining)
                except Exception as e:
                    print(f"Ошибка dry_target: {e}")
                    dry_target = now + timedelta(hours=dry_time_hours)
            elif dry_time_hours > 0:
                dry_target = now + timedelta(hours=dry_time_hours)
            else:
                dry_time_hours = 0
                dry_target = now

            is_asphalt = park.get("soil") == "asphalt"
            soil_status = get_soil_status(rain_total, dry_time_hours, hours_since_rain, is_asphalt)

            results.append({
                "park": {
                    "id": park["id"],
                    "name": park["name"],
                    "lat": park["lat"],
                    "lon": park["lon"],
                    "dryHours": round(dry_time_hours, 1),
                    "startDate": park.get("start_date"),
                    "soil": park.get("soil", "loam"),
                    "forest": park.get("forest", True),
                    "forest_coef": park.get("forest_coef", FOREST_COEFFICIENT),
                    "rain_6d": round(rain_history, 1),
                    "rain_forecast": round(rain_forecast, 1),
                    "rain_total": round(rain_total, 1),
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
                    "soil": park.get("soil", "loam"),
                    "forest": park.get("forest", True),
                    "forest_coef": park.get("forest_coef", FOREST_COEFFICIENT),
                    "rain_6d": 0,
                    "rain_forecast": 0,
                    "rain_total": 0,
                    "soilStatus": "Нет данных",
                    "dryTarget": None
                },
                "forecast": None,
                "history": None,
                "provider": "openmeteo",
                "error": str(e)
            })

    return results