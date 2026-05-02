import httpx
import asyncio
from typing import Optional
from datetime import datetime, timedelta

_cache = {}

async def fetch_with_retry(url: str, retries: int = 3) -> Optional[dict]:
    for i in range(retries):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            if i == retries - 1:
                print(f"Open-Meteo: ошибка после {retries} попыток: {e}")
                return None
            print(f"Open-Meteo: попытка {i+1}/{retries}: {e}")
            await asyncio.sleep(1 * (i + 1))

async def get_forecast(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"forecast_{lat:.4f}_{lon:.4f}"
    if cache_key in _cache:
        print("✅ Кэш (прогноз)")
        return _cache[cache_key]

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code,wind_speed_10m"
        f"&hourly=temperature_2m,weather_code,rain,wind_speed_10m"
        f"&daily=temperature_2m_max,rain_sum,weather_code"
        f"&timezone=auto&forecast_hours=6&forecast_days=6"
    )
    
    print(f"🌐 Open-Meteo: запрос прогноза...")
    data = await fetch_with_retry(url)
    if data:
        _cache[cache_key] = data
    return data

async def get_history(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"history_{lat:.4f}_{lon:.4f}"
    if cache_key in _cache:
        print("✅ Кэш (история)")
        return _cache[cache_key]

    now = datetime.now()
    end_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly=rain&timezone=auto"
    )
    
    print(f"🌐 Open-Meteo: запрос истории...")
    data = await fetch_with_retry(url)
    if data:
        _cache[cache_key] = data
    return data