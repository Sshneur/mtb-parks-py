from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta, timezone
from database.crud import get_parks_by_group
from database.connection import get_connection
from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status
from api.utils import parse_time, to_msk, weather_code, MOSCOW_TZ, build_forecast, build_daily_from_db
from api.cache import get_cached, set_cached
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/groups")
async def get_groups():
    try:
        from database.crud import get_all_parks
        parks = get_all_parks()
        groups = {}
        for park in parks:
            gid = park["group_id"]
            if gid not in groups:
                groups[gid] = {"id": gid, "name": _get_group_name(gid)}
        return [{"id": gid, "name": groups[gid]["name"]} for gid in groups]
    except Exception as e:
        logger.error(f"Ошибка в get_groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/api/weather/{group_id}")
async def get_weather(group_id: str):
    cached = get_cached(f"weather_{group_id}")
    if cached:
        return cached
    try:
        parks = get_parks_by_group(group_id)
        if not parks:
            return {"error": "Группа не найдена"}

        results = []
        conn = get_connection()
        try:
            for park in parks:
                park_id = park["id"]

                now_utc = datetime.now(timezone.utc)
                now_iso = now_utc.isoformat()
                hour_start = now_utc.replace(minute=0, second=0, microsecond=0)
                hour_start_str = hour_start.strftime("%Y-%m-%dT%H:%M")

                rows = conn.execute("""
                    SELECT * FROM weather_hourly
                    WHERE park_id = ?
                      AND timestamp >= datetime('now', '-14 days')
                      AND (timestamp <= ? OR (source = 'forecast' AND timestamp >= ?))
                    ORDER BY timestamp ASC
                """, (park_id, now_iso, hour_start_str)).fetchall()

                all_rows = []
                forecast_rows = []
                current_hour_row = None
                for r in rows:
                    if r["timestamp"] <= now_iso:
                        all_rows.append(r)
                    if r["source"] == "forecast" and r["timestamp"] >= hour_start_str:
                        forecast_rows.append(r)
                    if current_hour_row is None and r["source"] == "history" and r["timestamp"] >= hour_start_str:
                        current_hour_row = r

                all_data = [dict(r) for r in all_rows]
                forecast_data = [dict(r) for r in forecast_rows]

                if current_hour_row is not None:
                    current_real = dict(current_hour_row)
                    current_real["source"] = "forecast"
                    if forecast_data:
                        forecast_data[0] = current_real
                    else:
                        forecast_data = [current_real]

                if all_data:
                    moisture = calculate_soil_moisture_from_db(park, all_data)
                    is_asphalt = park.get("soil_type") == "asphalt"
                    status = get_soil_status(
                        moisture["total_rain"],
                        moisture["dry_hours"],
                        moisture["hours_since_rain"],
                        is_asphalt
                    )

                    if moisture["dry_hours"] > 0:
                        dry_target_utc = now_utc + timedelta(hours=moisture["dry_hours"])
                        dry_target_str = dry_target_utc.timestamp() * 1000
                    else:
                        dry_target_str = None

                    forecast = build_forecast(
                        forecast_data if forecast_data else all_data[-6:],
                        hour_start,
                        daily_data={"daily": build_daily_from_db(conn, park_id)}
                    )

                    history = {
                        "hourly": {
                            "time": [to_msk(h["timestamp"]) for h in all_data],
                            "rain": [h.get("rain") or 0 for h in all_data]
                        }
                    }

                    results.append({
                        "park": {
                            "id": park["id"],
                            "name": park["name"],
                            "lat": park["lat"],
                            "lon": park["lon"],
                            "dryHours": moisture["dry_hours"],
                            "startDate": park.get("start_date"),
                            "soil": park["soil_type"],
                            "forest": True,
                            "forest_coef": park["forest_coef"],
                            "rain_6d": moisture["total_rain"],
                            "rain_forecast": 0,
                            "rain_total": sum(h.get("rain", 0) or 0 for h in all_data if parse_time(h["timestamp"]) >= (datetime.now(timezone.utc) - timedelta(days=6))),
                            "current_moisture": moisture["current_moisture"],
                            "soilStatus": status,
                            "dryTarget": dry_target_str
                        },
                        "forecast": forecast,
                        "history": history,
                        "provider": "openmeteo",
                        "error": None
                    })
                else:
                    results.append({
                        "park": {
                            "id": park["id"],
                            "name": park["name"],
                            "lat": park["lat"],
                            "lon": park["lon"],
                            "dryHours": 0,
                            "startDate": None,
                            "soil": park["soil_type"],
                            "forest": True,
                            "forest_coef": park["forest_coef"],
                            "rain_6d": 0,
                            "rain_forecast": 0,
                            "rain_total": 0,
                            "current_moisture": 0,
                            "soilStatus": "Нет данных ⏳",
                            "dryTarget": None
                        },
                        "forecast": None,
                        "history": None,
                        "provider": "openmeteo",
                        "error": "Парк ожидает инициализации"
                    })
        finally:
            conn.close()

        set_cached(f"weather_{group_id}", results)
        return results
    except Exception as e:
        logger.error(f"Ошибка в get_weather: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


def _get_group_name(group_id: str) -> str:
    names = {"mtb_parks": "МТБ Парки", "mtb_mountains": "МТБ Горы", "pamps": "Пампы"}
    return names.get(group_id, group_id)
