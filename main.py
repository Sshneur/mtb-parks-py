from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

from api.weather_routes import router as weather_router

load_dotenv()

app = FastAPI(title="МТБ Парки 2.0 (Python)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(weather_router)

# Попробуем подключить статику
import os as _os
static_path = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.exists(static_path):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print("=" * 50)
    print("  🚵 МТБ Парки 2.0 (Python) — сервер запущен")
    print("  🌐 http://localhost:8000")
    print("  📡 API: http://localhost:8000/api/weather/all")
    print("=" * 50)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)