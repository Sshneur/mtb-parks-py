from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import logging
import os as _os
from datetime import datetime

# Загружаем .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Создаём приложение
app = FastAPI(title="МТБ Парки 2.0 (Python)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для логирования всех запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.2f}с)")
    return response

# API-роуты
from api.weather_routes import router as weather_router
app.include_router(weather_router)

# Раздача статики (фронтенд)
static_path = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.exists(static_path):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Точка входа
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("  🚵 МТБ Парки 2.0 (Python) — сервер запущен")
    logger.info("  🌐 http://localhost:8000")
    logger.info("  📡 API: http://localhost:8000/api/weather/all")
    logger.info("=" * 50)
    print("=" * 50)
    print("  🚵 МТБ Парки 2.0 (Python) — сервер запущен")
    print("  🌐 http://localhost:8000")
    print("  📡 API: http://localhost:8000/api/weather/all")
    print("=" * 50)
    uvicorn.run("main:app", host="0.0.0.0", port=8000)