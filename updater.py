import asyncio
from datetime import datetime, timedelta, timezone
from database.connection import get_connection
from database.crud import (
    get_all_parks, count_weather_records,
    insert_weather_hourly, update_park_moisture, log_update
)
from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status
from services.open_meteo import get_history, get_forecast


async def initialize_park(park: dict):
    """Первый запуск: загружаем историю за 30 дней"""
    park_id = park["id"]
    print(f"🔄 Инициализация {park['name']}...")
    
    try:
        history = await get_history(park["lat"], park["lon"], days=30)
        
        if history and history.get("hourly"):
            hourly = history["hourly"]
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rains = hourly.get("rain", [])
            winds = hourly.get("wind_speed_10m", [])
            rads = hourly.get("shortwave_radiation", [])
            
            count = 0
            for i, t in enumerate(times):
                inserted = insert_weather_hourly(
                    park_id=park_id,
                    timestamp=t,
                    temperature=temps[i] if i < len(temps) else None,
                    rain=rains[i] if i < len(rains) else 0,
                    wind_speed=winds[i] if i < len(winds) else None,
                    radiation=rads[i] if i < len(rads) else None,
                    source="history"
                )
                if inserted:
                    count += 1
            
            print(f"  ✅ Загружено {count} записей истории")
            log_update(park_id, "history", "success", f"Загружено {count} записей")
        else:
            print(f"  ⚠️ История пуста")
            log_update(park_id, "history", "failed", "Пустой ответ API")
            return
    
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        log_update(park_id, "history", "failed", str(e))
        return
    
    _recalculate_moisture(park)


async def update_forecast(park: dict):
    """Обновление прогноза (каждые 30 минут)"""
    park_id = park["id"]
    
    try:
        forecast = await get_forecast(park["lat"], park["lon"])
        
        if forecast and forecast.get("hourly"):
            hourly = forecast["hourly"]
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rains = hourly.get("rain", [])
            winds = hourly.get("wind_speed_10m", [])
            rads = hourly.get("shortwave_radiation", [])
            
            count = 0
            for i, t in enumerate(times):
                inserted = insert_weather_hourly(
                    park_id=park_id,
                    timestamp=t,
                    temperature=temps[i] if i < len(temps) else None,
                    rain=rains[i] if i < len(rains) else 0,
                    wind_speed=winds[i] if i < len(winds) else None,
                    radiation=rads[i] if i < len(rads) else None,
                    source="forecast"
                )
                if inserted:
                    count += 1
            
            if count > 0:
                print(f"  📡 {park['name']}: +{count} новых часов прогноза")
            log_update(park_id, "forecast", "success", f"Новых записей: {count}")
        else:
            log_update(park_id, "forecast", "failed", "Пустой ответ API")
            return
        
    except Exception as e:
        print(f"  ❌ Ошибка прогноза для {park['name']}: {e}")
        log_update(park_id, "forecast", "failed", str(e))
        return
    
    _recalculate_moisture(park)


def _recalculate_moisture(park: dict):
    """Пересчитывает влажность по ВСЕМ данным и сохраняет в БД"""
    park_id = park["id"]
    
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM weather_hourly 
        WHERE park_id = ? 
        ORDER BY timestamp ASC
    """, (park_id,)).fetchall()
    conn.close()
    
    hourly_data = [dict(r) for r in rows]
    
    if not hourly_data:
        print(f"  ⚠️ {park['name']}: нет данных для расчёта")
        return
    
    result = calculate_soil_moisture_from_db(park, hourly_data)
    update_park_moisture(park_id, result["current_moisture"])
    
    is_asphalt = park.get("soil_type") == "asphalt"
    status = get_soil_status(
        result["total_rain"],
        result["dry_hours"],
        result["hours_since_rain"],
        is_asphalt
    )
    
    print(f"  💧 {park['name']}: W={result['current_moisture']:.3f}, "
          f"dry={result['dry_hours']:.1f}h, rain={result['total_rain']:.1f}mm, "
          f"status={status}")


async def daily_history_update():
    """Раз в сутки запрашивает фактические данные за вчерашний день"""
    parks = get_all_parks()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for park in parks:
        try:
            history = await get_history(park["lat"], park["lon"], days=1)
            if history and history.get("hourly"):
                hourly = history["hourly"]
                times = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])
                rains = hourly.get("rain", [])
                winds = hourly.get("wind_speed_10m", [])
                rads = hourly.get("shortwave_radiation", [])
                
                count = 0
                for i, t in enumerate(times):
                    inserted = insert_weather_hourly(
                        park_id=park["id"],
                        timestamp=t,
                        temperature=temps[i] if i < len(temps) else None,
                        rain=rains[i] if i < len(rains) else 0,
                        wind_speed=winds[i] if i < len(winds) else None,
                        radiation=rads[i] if i < len(rads) else None,
                        source="history"
                    )
                    if inserted:
                        count += 1
                
                print(f"📅 {park['name']}: обновлено {count} часов за {yesterday}")
                log_update(park["id"], "history_daily", "success", f"Обновлено {count} часов за {yesterday}")
        except Exception as e:
            print(f"❌ Ошибка при обновлении факта для {park['name']}: {e}")
            log_update(park["id"], "history_daily", "failed", str(e))
        
        _recalculate_moisture(park)


async def run_updater():
    """Основной цикл обновления"""
    print("🔄 Запуск планировщика обновлений...")
    
    parks = get_all_parks()
    for park in parks:
        count = count_weather_records(park["id"])
        if count == 0:
            await initialize_park(park)
        else:
            await update_forecast(park)
    
        print(f"✅ Инициализация завершена. Начинаю обновление прогноза...")
    
    # ПЕРВОЕ обновление сразу после инициализации (без ожидания 30 минут)
    parks = get_all_parks()
    for park in parks:
        await update_forecast(park)
    
    print(f"🔄 Первичное обновление завершено. Далее каждые 30 минут.")
    
    last_daily_update = datetime.now(timezone.utc).date()
    
    while True:
        now = datetime.now(timezone.utc)
        # Ежедневное обновление факта в 01:00 UTC
        if now.date() > last_daily_update and now.hour >= 1:
            print("📅 Запуск ежедневного обновления фактических данных...")
            await daily_history_update()
            last_daily_update = now.date()
        
        await asyncio.sleep(1800)  # 30 минут
        
        parks = get_all_parks()
        for park in parks:
            await update_forecast(park)
        
        print(f"🔄 Цикл обновления завершён. Следующий через 30 минут.")