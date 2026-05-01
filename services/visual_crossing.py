import httpx
import os
from typing import Optional

_cache = {}

async def fetch_json(url: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            if response.status_code == 429:
                print("Visual Crossing: лимит исчерпан (429)")
                return None
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Visual Crossing: ошибка: {e}")
        return None

def map_icon_to_wmo(icon: str) -> int:
    icon_map = {
        "clear-day": 0, "clear-night": 0,
        "partly-cloudy-day": 1, "partly-cloudy-night": 1,
        "cloudy": 3, "rain": 61,
        "showers-day": 80, "showers-night": 80,
        "thunder-rain": 95, "thunder-showers-day": 95, "thunder-showers-night": 95,
        "snow": 71, "snow-showers-day": 85, "snow-showers-night": 85,
        "fog": 45, "wind": 3
    }
    return icon_map.get(icon, 3)

async def get_forecast(lat: float, lon: float) -> Optional[dict]:
    cache_key = f"vc_forecast_{lat:.4f}_{lon:.4f}"
    if cache_key in _cache:
        print("✅ VC Кэш (прогноз)")
        return _cache[cache_key]

    api_key = os.getenv("VISUAL_CROSSING_KEY")
    if not api_key:
        return None

    url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
        f"?unitGroup=metric&include=hours,days,current&lang=ru&key={api_key}&contentType=json"
    )
    
    print(f"🌐 VC: запрос прогноза для {lat:.4f},{lon:.4f}...")
    data = await fetch_json(url)
    if not data:
        return None

    result = {
        "current": None,
        "hourly": {"time": [], "temperature_2m": [], "weather_code": [], "rain": []},
        "daily": {"time": [], "temperature_2m_max": [], "rain_sum": [], "weather_code": []}
    }

    if "currentConditions" in data:
        result["current"] = {
            "temperature_2m": data["currentConditions"]["temp"],
            "weather_code": map_icon_to_wmo(data["currentConditions"]["icon"])
        }

    days = data.get("days", [])
    if days:
        for hour in days[0].get("hours", [])[:6]:
            result["hourly"]["time"].append(hour["datetime"])
            result["hourly"]["temperature_2m"].append(hour["temp"])
            result["hourly"]["weather_code"].append(map_icon_to_wmo(hour["icon"]))
            result["hourly"]["rain"].append(hour.get("precip", 0))

        for day in days[:6]:
            result["daily"]["time"].append(day["datetime"])
            result["daily"]["temperature_2m_max"].append(day["tempmax"])
            result["daily"]["rain_sum"].append(day.get("precip", 0))
            result["daily"]["weather_code"].append(map_icon_to_wmo(day["icon"]))

    _cache[cache_key] = result
    print("✅ VC: прогноз получен")
    return result

async def get_history(lat: float, lon: float) -> Optional[dict]:
    from datetime import datetime, timedelta
    
    cache_key = f"vc_history_{lat:.4f}_{lon:.4f}"
    if cache_key in _cache:
        print("✅ VC Кэш (история)")
        return _cache[cache_key]

    api_key = os.getenv("VISUAL_CROSSING_KEY")
    if not api_key:
        return None

    now = datetime.now()
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")

    url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}/{start_date}/{end_date}"
        f"?unitGroup=metric&include=hours&lang=ru&key={api_key}&contentType=json"
    )
    
    print(f"🌐 VC: запрос истории для {lat:.4f},{lon:.4f}...")
    data = await fetch_json(url)
    if not data:
        return None

    result = {"hourly": {"time": [], "rain": []}}
    for day in data.get("days", []):
        for hour in day.get("hours", []):
            result["hourly"]["time"].append(hour["datetime"])
            result["hourly"]["rain"].append(hour.get("precip", 0))

    _cache[cache_key] = result
    print("✅ VC: история получена")
    return result