import httpx
import asyncio
import time
from typing import Optional
from datetime import datetime, timedelta

_cache = {}
CACHE_TTL_FORECAST = 5 * 60
CACHE_TTL_HISTORY = 15 * 60

def get_from_cache(key: str) -> Optional[dict]:
    if key in _cache:
        entry = _cache[key]
        if time.time() - entry["timestamp"] < entry["ttl"]:
            return entry["data"]
        else:
            del _cache[key]
    return None

def set_to_cache(key: str, data: dict, ttl: int):
    _cache[key] = {"data": data, "timestamp": time.time(), "ttl": ttl}

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
    cached = get_from_cache(cache_key)
    if cached:
        print("✅ Кэш (прогноз)")
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code,wind_speed_10m,shortwave_radiation"
        f"&hourly=temperature_2m,weather_code,rain,wind_speed_10m"
        f"&daily=temperature_2m_max,rain_sum,weather_code"
        f"&timezone=Europe%2FMoscow&forecast_hours=6&forecast_days=6"
    )
    
    print(f"🌐 Open-Meteo: запрос прогноза...")
    data = await fetch_with_retry(url)
    if data:
        set_to_cache(cache_key, data, CACHE_TTL_FORECAST)
    return data

async def get_history(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"history_{lat:.4f}_{lon:.4f}"
    cached = get_from_cache(cache_key)
    if cached:
        print("✅ Кэш (история)")
        return cached

    now = datetime.now()
    end_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")

    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly=rain&timezone=UTC"
    )
    
    print(f"🌐 Open-Meteo: запрос истории...")
    data = await fetch_with_retry(url)
    if data:
        set_to_cache(cache_key, data, CACHE_TTL_HISTORY)
    return data