from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
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


# ============================================================
# Жизненный цикл приложения: инициализация БД и планировщика
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускается при старте сервера и завершении"""
    print("=" * 50)
    print("  🚵 МТБ Парки 2.0 — инициализация...")
    print("=" * 50)
    
    # Инициализируем БД
    from database.connection import init_db
    init_db()
    
    # Переносим парки если нужно
    from database.crud import seed_parks
    seed_parks()
    
    # Применяем миграцию (добавляем таблицы пользователей)
    try:
        from migrations.add_users_and_favorites import migrate
        migrate()
    except Exception as e:
        print(f"⚠️ Миграция пропущена: {e}")
    
    # Запускаем планировщик обновлений в фоне
    import asyncio
    from updater import run_updater
    updater_task = asyncio.create_task(run_updater())
    
    print("=" * 50)
    print("  ✅ Сервер готов к работе")
    print("  🌐 http://localhost:8000")
    print("=" * 50)
    
    yield  # Сервер работает
    
    # Завершение
    updater_task.cancel()
    try:
        await updater_task
    except asyncio.CancelledError:
        pass
    print("Сервер остановлен")


# Создаём приложение
app = FastAPI(
    title="МТБ Парки 2.0 (Python)",
    lifespan=lifespan
)

# Rate Limiter
from slowapi.errors import RateLimitExceeded
from api.limiter import limiter
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Слишком много запросов. Подождите."})

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для логирования всех запросов (из middleware.py)
from middleware import log_request
app.middleware("http")(log_request)

# API-роуты
from api.weather_routes import router as weather_router
app.include_router(weather_router)

from api.auth_routes import router as auth_router
app.include_router(auth_router)

from api.user_routes import router as user_router
app.include_router(user_router)

from api.admin_routes import router as admin_router
app.include_router(admin_router)

from api.votes_routes import router as votes_router
app.include_router(votes_router)

# Раздача статики (фронтенд)
static_path = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.exists(static_path):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Точка входа
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)