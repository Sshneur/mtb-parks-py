from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config.parks import PARKS
from services import open_meteo
import os

router = APIRouter()

@router.get("/api/parks")
async def get_parks():
    return PARKS

@router.get("/api/weather/all")
async def get_weather_all():
    results = []

    for park in PARKS:
        try:
            print(f"Запрос для {park['name']}...")
            forecast = await open_meteo.get_forecast(park["lat"], park["lon"])
            history = await open_meteo.get_history(park["lat"], park["lon"])

            park_camel = {
                "id": park["id"],
                "name": park["name"],
                "lat": park["lat"],
                "lon": park["lon"],
                "dryHours": park["dry_hours"],
                "startDate": park["start_date"]
            }

            results.append({
                "park": park_camel,
                "forecast": forecast,
                "history": history,
                "provider": "openmeteo",
                "error": None
            })
        except Exception as e:
            print(f"Ошибка для {park['name']}: {e}")
            park_camel = {
                "id": park["id"],
                "name": park["name"],
                "lat": park["lat"],
                "lon": park["lon"],
                "dryHours": park["dry_hours"],
                "startDate": park["start_date"]
            }
            results.append({
                "park": park_camel,
                "forecast": None,
                "history": None,
                "provider": "openmeteo",
                "error": str(e)
            })

    return results