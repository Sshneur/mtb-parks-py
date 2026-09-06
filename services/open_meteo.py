import httpx
import asyncio
import time
import random
from typing import Optional
from datetime import datetime, timedelta
import os

PROXY_URL = os.getenv("PROXY_URL")

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


def parse_openmeteo_response(data: dict) -> list[dict]:
    """Извлекает почасовые данные из ответа Open-Meteo"""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    rains = hourly.get("rain", [])
    winds = hourly.get("wind_speed_10m", [])
    rads = hourly.get("shortwave_radiation", [])
    hums = hourly.get("relativehumidity_2m", [])
    press = hourly.get("surface_pressure", [])
    result = []
    for i, t in enumerate(times):
        result.append({
            "timestamp": t,
            "temperature": temps[i] if i < len(temps) else None,
            "rain": rains[i] if i < len(rains) else 0,
            "wind_speed": winds[i] if i < len(winds) else None,
            "radiation": rads[i] if i < len(rads) else None,
            "relative_humidity": hums[i] if i < len(hums) else None,
            "surface_pressure": press[i] if i < len(press) else None,
        })
    return result

async def fetch_with_retry(url: str, retries: int = 3) -> Optional[dict]:
    for i in range(retries):
        try:
            if PROXY_URL:
                async with httpx.AsyncClient(proxy=PROXY_URL, timeout=15) as client:
                    response = await client.get(url)
            else:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if i == retries - 1:
                print(f"Open-Meteo: ошибка после {retries} попыток: {e}")
                return None
            wait = (2 ** i) + random.uniform(0, 1)
            print(f"Open-Meteo: попытка {i+1}/{retries} через {wait:.1f}с: {e}")
            await asyncio.sleep(wait)

async def get_forecast(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"forecast_{lat:.4f}_{lon:.4f}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,rain,wind_speed_10m,shortwave_radiation,relativehumidity_2m,surface_pressure"
        f"&daily=temperature_2m_max,rain_sum"
        f"&timezone=UTC&forecast_days=4"
    )
    print(f"Open-Meteo: запрос прогноза на 3 дня...")
    data = await fetch_with_retry(url)
    if data:
        set_to_cache(cache_key, data, CACHE_TTL_FORECAST)
    return data

async def get_history(lat: float, lon: float, days: int = 30) -> Optional[dict]:
    cache_key = f"history_{lat:.4f}_{lon:.4f}_{days}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    now = datetime.now()
    end_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly=temperature_2m,rain,wind_speed_10m,shortwave_radiation,relativehumidity_2m,surface_pressure"
        f"&timezone=UTC"
    )
    print(f"Open-Meteo: запрос истории за {days} дней...")
    data = await fetch_with_retry(url)
    if data:
        set_to_cache(cache_key, data, CACHE_TTL_HISTORY)
    return data

async def get_forecast_daily(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"daily_{lat:.4f}_{lon:.4f}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,rain_sum,weather_code"
        f"&timezone=UTC&forecast_days=7"
    )
    print(f"Open-Meteo: запрос дневного прогноза...")
    data = await fetch_with_retry(url)
    if data:
        set_to_cache(cache_key, data, CACHE_TTL_FORECAST)
    return data