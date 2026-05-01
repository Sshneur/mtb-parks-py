from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from config.parks import PARKS
from services import open_meteo
import os

router = APIRouter()
current_provider = os.getenv("WEATHER_PROVIDER", "openmeteo")

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
    print(f"Используем провайдер: {current_provider}")
    results = []
    
    for park in PARKS:
        try:
            print(f"Запрос для {park['name']}...")
            forecast = await open_meteo.get_forecast(park["lat"], park["lon"])
            history = await open_meteo.get_history(park["lat"], park["lon"])
            results.append({
                "park": park,
                "forecast": forecast,
                "history": history,
                "provider": current_provider,
                "error": None
            })
        except Exception as e:
            print(f"Ошибка для {park['name']}: {e}")
            results.append({
                "park": park,
                "forecast": None,
                "history": None,
                "provider": current_provider,
                "error": str(e)
            })
    
    return results