from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import uvicorn
import logging
import os as _os
from datetime import datetime

# Загружаем .env
load_dotenv()

# Фикс кодировки для Windows (emoji в print/log)
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    _sys.stdout.reconfigure(encoding='utf-8')
if hasattr(_sys.stderr, 'reconfigure'):
    _sys.stderr.reconfigure(encoding='utf-8')

# Настройка логирования
logging.basicConfig(
    filename=_os.getenv("LOG_FILE", "server.log"),
    level=getattr(logging, _os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Создаём папки при старте (до инициализации приложения)
_os.makedirs("data", exist_ok=True)
_os.makedirs("data/photos", exist_ok=True)


# ============================================================
# Жизненный цикл приложения: инициализация БД и планировщика
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускается при старте сервера и завершении"""
    print("=" * 50)
    print("  Где Держак? - init...")
    print("=" * 50)
    
    # Инициализируем БД
    from database.connection import init_db
    init_db()
    
    # Переносим парки если нужно
    from database.crud import seed_parks
    seed_parks()
    
    # Применяем миграции
    try:
        from migrations.add_users_and_favorites import migrate as m1
        m1()
    except Exception as e:
        print(f"Migration add_users skipped: {e}")
    try:
        from migrations.add_garage_tables import migrate as m2
        m2()
    except Exception as e:
        print(f"Migration add_garage skipped: {e}")
    
    # Применяем калибровку парков
    try:
        from database.crud import apply_park_calibration
        apply_park_calibration()
    except Exception as e:
        print(f"Calibration skipped: {e}")
    
    # Запускаем планировщик обновлений в фоне
    import asyncio
    from updater import run_updater
    updater_task = asyncio.create_task(run_updater())

    # Запускаем Telegram бота для модерации фото
    from telegram_bot import start_polling
    telegram_task = asyncio.create_task(start_polling())
    
    print("=" * 50)
    print("  Server ready")
    print("  http://localhost:8000")
    print("=" * 50)
    
    yield  # Сервер работает
    
    # Завершение
    updater_task.cancel()
    
    try:
        await updater_task
    except asyncio.CancelledError:
        pass
    print("Сервер остановлен")

    telegram_task.cancel()
    try:
        await telegram_task
    except asyncio.CancelledError:
        pass


# Создаём приложение
app = FastAPI(
    title="Что с грунтом? (Python)",
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

from api.pm_routes import router as pm_router
app.include_router(pm_router)

from api.park_routes import router as park_router
app.include_router(park_router)

from api.garage_routes import router as garage_router
app.include_router(garage_router)

# ============================================================
# СТАТИЧЕСКИЕ СТРАНИЦЫ (контакты, развитие проекта)
# ============================================================

CONTACTS_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Контакты — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <meta name="description" content="Свяжитесь со мной по Telegram для добавления новых парков и предложений.">
    <meta property="og:title" content="Контакты — Что с грунтом?">
    <meta property="og:description" content="Свяжитесь со мной по Telegram для добавления новых парков и предложений.">
    <meta property="og:image" content="https://gripchek.ru/og-image.jpg">
    <meta property="og:image:secure_url" content="https://gripchek.ru/og-image.jpg">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:url" content="https://gripchek.ru">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="ru_RU">
    <style>
        .contacts-container {
            max-width: 600px;
            margin: 60px auto;
            padding: 30px;
            background: rgba(18,22,30,0.9);
            border: 1px solid rgba(74,144,226,0.25);
            border-radius: 16px;
            text-align: center;
            color: #eef5ff;
        }
        .contacts-container h1 {
            font-size: 2rem;
            margin-bottom: 20px;
            color: #74a8e2;
        }
        .contacts-container .telegram-link {
            display: inline-block;
            margin: 20px 0;
            padding: 14px 28px;
            background: #0088cc;
            color: white;
            border-radius: 40px;
            text-decoration: none;
            font-size: 1.2rem;
            font-weight: 600;
            transition: background 0.3s;
        }
        .contacts-container .telegram-link:hover {
            background: #006699;
        }
        .contacts-container .message {
            font-size: 1.1rem;
            color: #b8d6ff;
            margin-top: 15px;
        }
        .back-link {
            display: inline-block;
            margin-top: 30px;
            color: #74a8e2;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="contacts-container">
        <h1>📞 Контакты</h1>
        <p>Свяжитесь со мной по Telegram:</p>
        <a href="https://t.me/sshhsss" target="_blank" class="telegram-link">@sshhsss</a>
        <div class="message">
            ❓ Если вашего парка нет в списке — напишите мне, и я добавлю его!
        </div>
        <a href="/" class="back-link">← На главную</a>
    </div>
</body>
</html>
"""

DEVELOPMENT_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Развитие проекта — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <meta name="description" content="Модели определения сухости грунта: физическая, ускоренная и пользовательская. Планы развития сервиса.">
    <meta property="og:title" content="Развитие проекта — Что с грунтом?">
    <meta property="og:description" content="Три модели расчёта влажности грунта и планы развития сервиса.">
    <meta property="og:image" content="https://gripchek.ru/og-image.jpg">
    <meta property="og:image:secure_url" content="https://gripchek.ru/og-image.jpg">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:url" content="https://gripchek.ru">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="ru_RU">
    <style>
        .dev-container {
            max-width: 700px;
            margin: 60px auto;
            padding: 30px;
            background: rgba(18,22,30,0.9);
            border: 1px solid rgba(74,144,226,0.25);
            border-radius: 16px;
            color: #eef5ff;
        }
        .dev-container h1 {
            font-size: 2rem;
            margin-bottom: 10px;
            color: #ffd966;
            text-align: center;
        }
        .dev-container .subtitle {
            text-align: center;
            color: #94afcf;
            font-size: 1rem;
            margin-bottom: 30px;
        }
        .dev-container p {
            font-size: 1.05rem;
            line-height: 1.6;
            color: #b8d6ff;
        }
        .dev-container .model-card {
            margin: 20px 0;
            padding: 20px;
            background: rgba(255,255,255,0.04);
            border-radius: 14px;
            border: 1px solid rgba(74,144,226,0.2);
        }
        .dev-container .model-card h3 {
            font-size: 1.15rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .dev-container .model-card p {
            font-size: 0.95rem;
            color: #c8dfff;
            margin: 0;
        }
        .dev-container .plan {
            margin: 30px 0;
            padding: 0;
            list-style: none;
        }
        .dev-container .plan li {
            padding: 16px 20px;
            margin: 10px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border-left: 4px solid #74a8e2;
            font-size: 1.02rem;
            color: #e2edff;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .dev-container .plan .icon {
            font-size: 1.5rem;
            flex-shrink: 0;
        }
        .dev-container .callout {
            margin-top: 30px;
            padding: 24px;
            background: linear-gradient(135deg, rgba(74,144,226,0.2), rgba(74,144,226,0.05));
            border-radius: 14px;
            text-align: center;
            border: 1px solid rgba(74,144,226,0.3);
        }
        .dev-container .callout a {
            color: #74a8e2;
            text-decoration: none;
            font-weight: 600;
        }
        .dev-container .callout a:hover {
            text-decoration: underline;
        }
        .back-link {
            display: inline-block;
            margin-top: 30px;
            color: #74a8e2;
            text-decoration: none;
            font-size: 1rem;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            .dev-container { margin: 20px 10px; padding: 20px; }
            .dev-container h1 { font-size: 1.5rem; }
        }
    </style>
</head>
<body>
    <div class="dev-container">
        <h1>🚀 Развитие проекта</h1>
        <p class="subtitle">Как мы определяем состояние грунта и что планируем дальше</p>

        <p style="margin-bottom:24px;">Мы используем <strong>три модели</strong> для расчёта влажности грунта на трассах. Каждая даёт свой прогноз — ты можешь сравнить их и выбрать тот, которому доверяешь больше.</p>

        <div class="model-card">
            <h3>🌡️ Физическая модель (OLD)</h3>
            <p>Рассчитывает испарение влаги по температуре, ветру, осадкам и солнечной радиации. Учитывает тип грунта (песок, глина, чернозём) и лесной покров. Надёжная и проверенная.</p>
        </div>

        <div class="model-card">
            <h3>⚡ Ускоренная модель (NEW)</h3>
            <p>Упрощённый алгоритм для быстрого прогноза. Использует те же метеоданные, но с меньшими вычислительными затратами. Хорошо работает в типичных условиях.</p>
        </div>

        <div class="model-card">
            <h3>👥 Пользовательская модель</h3>
            <p>Основана на реальных оценках райдеров — твоих и других пользователей. Если большинство отметило «Сухо» — значит сухо. Чем больше оценок, тем точнее результат. <strong>Ты можешь повлиять на прогноз!</strong></p>
        </div>

        <p style="margin-top:24px;">А вот что мы планируем сделать в ближайшее время:</p>
        <ul class="plan">
            <li>
                <span class="icon">🤖</span>
                <span><strong>ИИ определяет грунт по фото и погоде</strong><br>
                Обучаем нейросеть предсказывать состояние трасс по вашим фотографиям и метеоданным. 
                Каждое загруженное фото с оценкой грунта — это пример для обучения. Чем больше фото — тем точнее прогноз. <strong>Грузите ваши фото! 📸</strong></span>
            </li>
            <li>
                <span class="icon">📡</span>
                <span><strong>Установка тестового датчика влажности грунта</strong><br>
                Мы планируем разместить физический датчик (ESP8266 + ёмкостной сенсор) в одном из парков, 
                чтобы получать реальные показания влажности в режиме реального времени. Это позволит 
                сравнивать данные модели с реальностью и повысить точность прогнозов.</span>
            </li>
            <li>
                <span class="icon">🗺️</span>
                <span><strong>Карта всех парков с состоянием грунта</strong><br>
                Уже работает! Открывай карту в меню и смотри состояние всех трасс сразу. Цветные маркеры показывают где сухо, где мокро, а где болото.</span>
            </li>
        </ul>
        <div class="callout">
            <p>💡 <strong>Хотите помочь или предложить идею?</strong><br>
            Напишите мне в Telegram: <a href="https://t.me/sshhsss" target="_blank">@sshhsss</a></p>
            <p style="font-size:0.9rem; color:#94afcf; margin-top:8px;">
                Мы открыты к сотрудничеству и новым идеям!
            </p>
        </div>
        <a href="/" class="back-link">← На главную</a>
    </div>
</body>
</html>
"""

@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page():
    return HTMLResponse(content=CONTACTS_HTML)

@app.get("/development", response_class=HTMLResponse)
async def development_page():
    return HTMLResponse(content=DEVELOPMENT_HTML)



@app.get("/profile", response_class=RedirectResponse)
async def profile_page():
    return RedirectResponse(url="/garage")

# ============================================================
# РАЗДАЧА СТАТИКИ
# ============================================================

# Раздача папки с фотографиями (ДО корневой статики, чтобы /photos не перехватывался)
photos_path = _os.path.join(_os.path.dirname(__file__), "data", "photos")
if _os.path.exists(photos_path):
    app.mount("/photos", StaticFiles(directory=photos_path), name="photos")

# Раздача статики (фронтенд) – должна быть последней
static_path = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.exists(static_path):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ============================================================
# ТОЧКА ВХОДА
# ============================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)