from fastapi import APIRouter
from config.parks import PARKS
from services import open_meteo

router = APIRouter()

@router.get("/api/groups")
async def get_groups():
    return [{"id": gid, "name": PARKS[gid]["name"]} for gid in PARKS]

@router.get("/api/weather/{group_id}")
async def get_weather(group_id: str = "mtb_parks"):
    if group_id not in PARKS:
        return {"error": "Группа не найдена"}
    
    parks = PARKS[group_id]["parks"]
    results = []

    for park in parks:
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
                "error": str(e)
            })

    return results