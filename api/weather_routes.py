from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
from database.crud import get_parks_by_group
from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status

MOSCOW_TZ = timezone(timedelta(hours=3))
router = APIRouter()


def _parse_time(t) -> datetime:
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except:
        dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_msk(t) -> str:
    dt = _parse_time(t)
    msk = dt.astimezone(MOSCOW_TZ)
    return msk.strftime("%Y-%m-%dT%H:%M")


def _weather_code(temp: float, rain: float) -> int:
    if rain and rain > 2:
        return 63
    elif rain and rain > 0.5:
        return 61
    elif rain and rain > 0:
        return 80
    elif temp and temp > 25:
        return 1
    elif temp and temp > 15:
        return 2
    else:
        return 3


@router.get("/api/groups")
async def get_groups():
    from database.crud import get_all_parks
    parks = get_all_parks()
    groups = {}
    for park in parks:
        gid = park["group_id"]
        if gid not in groups:
            groups[gid] = {"id": gid, "name": _get_group_name(gid)}
    return [{"id": gid, "name": groups[gid]["name"]} for gid in groups]


@router.get("/api/weather/{group_id}")
async def get_weather(group_id: str):
    parks = get_parks_by_group(group_id)
    if not parks:
        return {"error": "Группа не найдена"}
    
    results = []
    for park in parks:
        park_id = park["id"]
        
        from database.connection import get_connection
        conn = get_connection()
        
        # Все данные для расчёта влажности
        all_rows = conn.execute("""
            SELECT * FROM weather_hourly 
            WHERE park_id = ? 
            ORDER BY timestamp ASC
        """, (park_id,)).fetchall()
        
        # Почасовой прогноз (начиная с текущего часа)
        now_utc = datetime.now(timezone.utc)
        hour_start = now_utc.replace(minute=0, second=0, microsecond=0)
        hour_start_str = hour_start.strftime("%Y-%m-%dT%H:%M")
        
        forecast_rows = conn.execute("""
            SELECT * FROM weather_hourly 
            WHERE park_id = ? AND source = 'forecast' AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (park_id, hour_start_str)).fetchall()
        
        conn.close()
        
        all_data = [dict(r) for r in all_rows]
        forecast_data = [dict(r) for r in forecast_rows]
        
        if all_data:
            moisture = calculate_soil_moisture_from_db(park, all_data)
            is_asphalt = park.get("soil_type") == "asphalt"
            status = get_soil_status(
                moisture["total_rain"],
                moisture["dry_hours"],
                moisture["hours_since_rain"],
                is_asphalt
            )
            
            # dryTarget в миллисекундах
            if moisture["dry_hours"] > 0:
                dry_target_utc = now_utc + timedelta(hours=moisture["dry_hours"])
                dry_target_str = dry_target_utc.timestamp() * 1000
            else:
                dry_target_str = None
            
            # Почасовой прогноз из БД
            forecast = _build_forecast(
                forecast_data if forecast_data else all_data[-6:],
                hour_start,
                daily_data=None
            )
            
            # Дневной прогноз – получаем отдельно через get_forecast_daily
            try:
                from services.open_meteo import get_forecast_daily
                daily_data = await get_forecast_daily(park["lat"], park["lon"])
                if daily_data and "daily" in daily_data:
                    forecast["daily"] = daily_data["daily"]
            except Exception as e:
                print(f"Не удалось получить daily для {park['name']}: {e}")
            
            history = {
                "hourly": {
                    "time": [_to_msk(h["timestamp"]) for h in all_data],
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
                    "rain_total": sum(
                h.get("rain", 0) or 0
                for h in all_data
                if _parse_time(h["timestamp"]) >= (datetime.now(timezone.utc) - timedelta(days=7))
            ),
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
    
    return results


def _build_forecast(forecast_data: list, hour_start: datetime, daily_data: dict = None) -> dict:
    """Строит forecast: почасовой из БД, дневной из daily_data"""
    
    future_hours = []
    for h in forecast_data:
        t = _parse_time(h["timestamp"])
        if t >= hour_start:
            future_hours.append(h)
        if len(future_hours) >= 6:
            break
    
    if len(future_hours) < 6:
        future_hours = forecast_data[-6:] if forecast_data else []
    
    hourly_forecast = {
        "time": [_to_msk(h["timestamp"]) for h in future_hours],
        "temperature_2m": [h.get("temperature") or 15 for h in future_hours],
        "rain": [h.get("rain") or 0 for h in future_hours],
        "weather_code": [
            _weather_code(h.get("temperature"), h.get("rain"))
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


def _get_group_name(group_id: str) -> str:
    names = {"mtb_parks": "МТБ Парки", "mtb_mountains": "МТБ Горы", "pamps": "Пампы"}
    return names.get(group_id, group_id)