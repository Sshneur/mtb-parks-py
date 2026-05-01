from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config.parks import PARKS
from services import open_meteo, visual_crossing
import os

router = APIRouter()
current_provider = os.getenv("WEATHER_PROVIDER", "openmeteo")

def get_provider():
    if current_provider == "visualcrossing" and os.getenv("VISUAL_CROSSING_KEY"):
        return visual_crossing
    return open_meteo

@router.get("/api/parks")
async def get_parks():
    return PARKS

@router.get("/api/provider")
async def get_provider_info():
    return {"provider": current_provider}

@router.post("/api/provider")
async def set_provider(request: Request):
    global current_provider
    data = await request.json()
    provider = data.get("provider")
    if provider in ["openmeteo", "visualcrossing"]:
        current_provider = provider
        print(f"✅ Провайдер изменён на: {current_provider}")
        return {"success": True, "provider": current_provider}
    return JSONResponse({"error": "Неверный провайдер"}, status_code=400)

@router.get("/api/weather/all")
async def get_weather_all():
    provider = get_provider()
    print(f"Используем провайдер: {current_provider}")
    results = []

    for park in PARKS:
        try:
            print(f"Запрос для {park['name']}...")
            forecast = await provider.get_forecast(park["lat"], park["lon"])
            history = await provider.get_history(park["lat"], park["lon"])

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
                "provider": current_provider,
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
                "provider": current_provider,
                "error": str(e)
            })

    return results