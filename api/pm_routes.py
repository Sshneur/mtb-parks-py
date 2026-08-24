from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
from database.crud import get_parks_by_group
from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation, wind_to_2m
from services.soil_calculator import get_soil_status
from api.utils import parse_time, to_msk, weather_code, build_forecast, build_daily_from_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

SURFACE_PARAMS = {
    "asphalt": {"z0m": 0.001, "d": 0, "r_s": 0},
    "sand": {"z0m": 0.005, "d": 0, "r_s": 70},
    "loam": {"z0m": 0.015, "d": 0.1, "r_s": 200},
    "clay": {"z0m": 0.015, "d": 0.1, "r_s": 150},
    "clay_heavy": {"z0m": 0.5, "d": 1.5, "r_s": 300},
    "chernozem": {"z0m": 0.015, "d": 0.1, "r_s": 100},
}


@router.get("/api/weather/pm/{group_id}")
async def get_weather_pm(group_id: str):
    try:
        parks = get_parks_by_group(group_id)
        if not parks:
            return []

        results = []
        conn = get_connection()
        try:
            for park in parks:
                park_id = park["id"]

                now_utc = datetime.now(timezone.utc)
                all_rows = conn.execute("""
                    SELECT * FROM weather_hourly
                    WHERE park_id = ? AND timestamp <= ? AND timestamp >= datetime('now', '-14 days')
                    ORDER BY timestamp ASC
                """, (park_id, now_utc.isoformat())).fetchall()

                hour_start = now_utc.replace(minute=0, second=0, microsecond=0)
                hour_start_str = hour_start.strftime("%Y-%m-%dT%H:%M")
                forecast_rows = conn.execute("""
                    SELECT * FROM weather_hourly
                    WHERE park_id = ? AND source = 'forecast' AND timestamp >= ?
                    ORDER BY timestamp ASC
                """, (park_id, hour_start_str)).fetchall()

                all_data = [dict(r) for r in all_rows]
                forecast_data = [dict(r) for r in forecast_rows]

                if all_data:
                    now = datetime.now(timezone.utc)
                    soil_type = park.get("soil_type", "loam")
                    surf = SURFACE_PARAMS.get(soil_type, SURFACE_PARAMS["loam"])
                    forest_coef = park.get("forest_coef", 0.3)

                    W = 0.0
                    W_max = 1.0
                    last_rain_time = None
                    total_rain = 0.0

                    for hour in all_data:
                        timestamp = parse_time(hour["timestamp"])
                        temp = hour.get("temperature") or 15
                        wind = wind_to_2m(hour.get("wind_speed") or 0)
                        rad = hour.get("radiation") or 0
                        rain = hour.get("rain") or 0
                        rel_hum = hour.get("relative_humidity")
                        press = hour.get("surface_pressure")

                        if rain > 0:
                            W = min(W_max, W + rain / 10)
                            total_rain += rain
                            last_rain_time = timestamp
                        else:
                            if rel_hum is None:
                                rel_hum = 70.0
                            if press is None:
                                press = 1013.0
                            evap = calc_pm_evaporation(
                                temp_c=temp,
                                wind_speed=wind,
                                radiation=rad,
                                relative_humidity=rel_hum,
                                pressure_pa=press * 100,
                                z0m=surf["z0m"],
                                d=surf["d"],
                                r_s=surf["r_s"]
                            )
                            evap *= forest_coef
                            W = max(0.0, W - evap / 10)

                    # ========== НОВОЕ: среднее испарение только за дневные часы последних 24 часов ==========
                    recent_evaps = []
                    for hour in all_data:
                        timestamp = parse_time(hour["timestamp"])
                        if (now_utc - timestamp).total_seconds() <= 86400:
                            hour_utc = timestamp.hour
                            rad = hour.get("radiation") or 0
                            # дневной час: радиация > 10 Вт/м² или время между 6 и 20 UTC
                            if rad > 10 or (6 <= hour_utc <= 20):
                                temp = hour.get("temperature") or 15
                                wind = wind_to_2m(hour.get("wind_speed") or 0)
                                rel_hum = hour.get("relative_humidity") or 70.0
                                press = hour.get("surface_pressure") or 1013.0
                                evap = calc_pm_evaporation(
                                    temp_c=temp, wind_speed=wind, radiation=rad,
                                    relative_humidity=rel_hum, pressure_pa=press * 100,
                                    z0m=surf["z0m"], d=surf["d"], r_s=surf["r_s"]
                                )
                                evap *= forest_coef
                                recent_evaps.append(evap)

                    if recent_evaps:
                        last_evap = sum(recent_evaps) / len(recent_evaps)
                    else:
                        last_evap = 0.001
                    # ========================================================================================

                    dry_hours = W / (last_evap / 10) if last_evap > 0 else 0
                    hours_since_rain = (now - last_rain_time).total_seconds() / 3600 if last_rain_time else None
                    is_asphalt = soil_type == "asphalt"
                    status = get_soil_status(total_rain, dry_hours, hours_since_rain, is_asphalt)

                    if dry_hours > 0:
                        dry_target_utc = now_utc + timedelta(hours=dry_hours)
                        dry_target_str = dry_target_utc.timestamp() * 1000
                    else:
                        dry_target_str = None

                    rain_7d = sum(
                        h.get("rain", 0) or 0
                        for h in all_data
                        if parse_time(h["timestamp"]) >= (datetime.now(timezone.utc) - timedelta(days=7))
                    )

                    forecast = build_forecast(
                        forecast_data if forecast_data else all_data[-6:],
                        hour_start,
                        daily_data={"daily": build_daily_from_db(conn, park_id)}
                    )

                    results.append({
                        "park": {
                            "id": park["id"],
                            "name": park["name"],
                            "lat": park["lat"],
                            "lon": park["lon"],
                            "dryHours": round(dry_hours, 1),
                            "dryTarget": dry_target_str,
                            "soil": soil_type,
                            "forest_coef": forest_coef,
                            "rain_total": round(rain_7d, 1),
                            "current_moisture": round(W, 3),
                            "soilStatus": status,
                            "model": "penman-monteith"
                        },
                        "forecast": forecast,
                        "history": None,
                        "provider": "openmeteo",
                        "error": None
                    })
                else:
                    results.append({
                        "park": {
                            "id": park["id"],
                            "name": park["name"],
                            "soilStatus": "Нет данных ⏳",
                            "model": "penman-monteith"
                        },
                        "forecast": None,
                        "history": None,
                        "error": "Нет данных для расчёта"
                    })
        finally:
            conn.close()

        return results
    except Exception as e:
        logger.error(f"Ошибка в /api/pm/forecast: {e}", exc_info=True)
        return {"error": "Внутренняя ошибка"}