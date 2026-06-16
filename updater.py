import asyncio
from datetime import datetime, timedelta, timezone
from database.connection import get_connection
from database.crud import (
    get_all_parks, count_weather_records,
    insert_weather_hourly, update_park_moisture, log_update
)
from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status
from services.open_meteo import get_history, get_forecast, get_forecast_daily, fetch_with_retry


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
            rel_hums = hourly.get("relativehumidity_2m", [])
            pressures = hourly.get("surface_pressure", [])
            
            count = 0
            for i, t in enumerate(times):
                inserted = insert_weather_hourly(
                    park_id=park_id,
                    timestamp=t,
                    temperature=temps[i] if i < len(temps) else None,
                    rain=rains[i] if i < len(rains) else 0,
                    wind_speed=winds[i] if i < len(winds) else None,
                    radiation=rads[i] if i < len(rads) else None,
                    source="history",
                    relative_humidity=rel_hums[i] if i < len(rel_hums) else None,
                    surface_pressure=pressures[i] if i < len(pressures) else None
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
            rel_hums = hourly.get("relativehumidity_2m", [])
            pressures = hourly.get("surface_pressure", [])
            
            count = 0
            for i, t in enumerate(times):
                inserted = insert_weather_hourly(
                    park_id=park_id,
                    timestamp=t,
                    temperature=temps[i] if i < len(temps) else None,
                    rain=rains[i] if i < len(rains) else 0,
                    wind_speed=winds[i] if i < len(winds) else None,
                    radiation=rads[i] if i < len(rads) else None,
                    source="forecast",
                    relative_humidity=rel_hums[i] if i < len(rel_hums) else None,
                    surface_pressure=pressures[i] if i < len(pressures) else None
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


async def update_daily_forecast(park: dict):
    """Обновление дневного прогноза (каждые 12 часов)"""
    park_id = park["id"]
    try:
        data = await get_forecast_daily(park["lat"], park["lon"])
        if data and "daily" in data:
            daily = data["daily"]
            times = daily.get("time", [])
            temps = daily.get("temperature_2m_max", [])
            rains = daily.get("rain_sum", [])
            codes = daily.get("weather_code", [])
            
            conn = get_connection()
            try:
                for i, t in enumerate(times):
                    conn.execute("""
                        INSERT OR REPLACE INTO weather_daily
                        (park_id, date, temperature_max, rain_sum, weather_code)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        park_id, t,
                        temps[i] if i < len(temps) else None,
                        rains[i] if i < len(rains) else 0,
                        codes[i] if i < len(codes) else None
                    ))
                conn.commit()
            finally:
                conn.close()
            print(f"  📅 {park['name']}: дневной прогноз обновлён на {len(times)} дней")
        else:
            print(f"  ⚠️ Дневной прогноз для {park['name']} пуст")
    except Exception as e:
        print(f"  ❌ Ошибка дневного прогноза для {park['name']}: {e}")


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
    """Раз в 3 часа запрашивает фактические данные за вчерашний день"""
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
                rel_hums = hourly.get("relativehumidity_2m", [])
                pressures = hourly.get("surface_pressure", [])
                
                count = 0
                for i, t in enumerate(times):
                    inserted = insert_weather_hourly(
                        park_id=park["id"],
                        timestamp=t,
                        temperature=temps[i] if i < len(temps) else None,
                        rain=rains[i] if i < len(rains) else 0,
                        wind_speed=winds[i] if i < len(winds) else None,
                        radiation=rads[i] if i < len(rads) else None,
                        source="history",
                        relative_humidity=rel_hums[i] if i < len(rel_hums) else None,
                        surface_pressure=pressures[i] if i < len(pressures) else None
                    )
                    if inserted:
                        count += 1
                
                print(f"📅 {park['name']}: обновлено {count} часов за {yesterday}")
                log_update(park["id"], "history_daily", "success", f"Обновлено {count} часов за {yesterday}")
        except Exception as e:
            print(f"❌ Ошибка при обновлении факта для {park['name']}: {e}")
            log_update(park["id"], "history_daily", "failed", str(e))
        
        _recalculate_moisture(park)


async def load_initial_daily_history():
    """Загружает архивные дневные данные за последние 7 дней для всех парков и сохраняет в weather_daily."""
    parks = get_all_parks()
    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # по вчерашний день

    for park in parks:
        try:
            url = (
                f"https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={park['lat']}&longitude={park['lon']}"
                f"&start_date={start_date}&end_date={end_date}"
                f"&daily=temperature_2m_max,rain_sum,weather_code"
                f"&timezone=UTC"
            )
            print(f"🌐 Open‑Meteo: запрос архивных дневных данных для {park['name']} ({start_date} – {end_date})...")
            data = await fetch_with_retry(url)
            if data and "daily" in data:
                daily = data["daily"]
                times = daily.get("time", [])
                temps = daily.get("temperature_2m_max", [])
                rains = daily.get("rain_sum", [])
                codes = daily.get("weather_code", [])

                conn = get_connection()
                try:
                    for i, t in enumerate(times):
                        conn.execute("""
                            INSERT OR REPLACE INTO weather_daily
                            (park_id, date, temperature_max, rain_sum, weather_code)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            park["id"], t,
                            temps[i] if i < len(temps) else None,
                            rains[i] if i < len(rains) else 0,
                            codes[i] if i < len(codes) else None
                        ))
                    conn.commit()
                finally:
                    conn.close()
                print(f"  ✅ {park['name']}: архивные дневные данные загружены ({len(times)} дней)")
            else:
                print(f"  ⚠️ {park['name']}: архивные дневные данные недоступны")
        except Exception as e:
            print(f"  ❌ Ошибка загрузки архивных дневных данных для {park['name']}: {e}")


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
    
    # Загружаем архивные дневные данные за последние 7 дней
    print("📊 Загрузка архивных дневных данных за 7 дней...")
    await load_initial_daily_history()
    
    # Первичная загрузка дневного прогноза
    for park in parks:
        await update_daily_forecast(park)
    
    print(f"✅ Инициализация завершена. Обновление каждые 30 минут (прогноз), каждые 12 часов (daily), каждые 3 часа (история).")
    
    last_history_update = datetime.now(timezone.utc) - timedelta(hours=3)
    last_daily_update = datetime.now(timezone.utc) - timedelta(hours=12)
    
    while True:
        now = datetime.now(timezone.utc)
        
        # Обновление факта (каждые 3 часа)
        if (now - last_history_update).total_seconds() >= 10800:
            print("📅 Запуск обновления фактических данных (каждые 3 часа)...")
            await daily_history_update()
            last_history_update = now
        
        # Обновление дневного прогноза (каждые 12 часов)
        if (now - last_daily_update).total_seconds() >= 43200:
            print("📊 Запуск обновления дневного прогноза (каждые 12 часов)...")
            for park in get_all_parks():
                await update_daily_forecast(park)
            last_daily_update = now
        
        await asyncio.sleep(1800)  # 30 минут
        
        parks = get_all_parks()
        for park in parks:
            await update_forecast(park)
        
        print(f"🔄 Цикл обновления завершён. Следующий через 30 минут.")