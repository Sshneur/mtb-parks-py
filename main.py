from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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
    print("  MTB Parks 2.0 - init...")
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
        print(f"Migration skipped: {e}")
    
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

    # Запускаем Telegram бота для модерации фото (пока отключён)
    # from telegram_bot import start_polling
    # telegram_task = asyncio.create_task(start_polling())
    
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

    # telegram_task.cancel()
    # try:
    #     await telegram_task
    # except asyncio.CancelledError:
    #     pass


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

PROFILE_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Профиль — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <meta property="og:title" content="Профиль — Что с грунтом?">
    <meta property="og:image" content="https://gripchek.ru/og-image.jpg">
    <style>
        .profile-container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .card { background:rgba(18,22,30,0.85); border:1px solid rgba(74,144,226,0.2); border-radius:14px; padding:16px; margin-bottom:16px; }
        .card h2 { font-size:1.1rem; color:#ffd966; margin-bottom:10px; }
        .bike-item { display:flex; align-items:center; gap:10px; padding:10px; background:rgba(255,255,255,0.04); border-radius:10px; margin-bottom:8px; }
        .bike-item .info { flex:1; }
        .bike-item .name { font-weight:600; color:#eef5ff; }
        .bike-item .detail { font-size:0.8rem; color:#94afcf; }
        .btn { display:inline-block; padding:10px 20px; border:none; border-radius:10px; font-size:0.9rem; cursor:pointer; font-weight:600; }
        .btn-primary { background:#4caf50; color:#fff; }
        .btn-danger { background:#e74c3c; color:#fff; }
        .btn-sm { padding:6px 12px; font-size:0.8rem; }
        input, select { width:100%; padding:10px; margin-bottom:8px; border:1px solid rgba(255,255,255,0.1); border-radius:8px; background:rgba(255,255,255,0.05); color:#eef5ff; font-size:0.9rem; }
        label { display:block; font-size:0.8rem; color:#94afcf; margin-bottom:3px; }
        #favList { text-align:center; }
        .fav-item { display:inline-block; padding:4px 10px; margin:3px; background:rgba(74,144,226,0.15); border-radius:6px; font-size:0.85rem; }
        #authRequired { text-align:center; padding:40px 20px; }
        #authRequired a { color:#74a8e2; }
        #bikeForm { display:none; }
        .avatar-img { width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid rgba(74,144,226,0.3); }
        .avatar-placeholder { width:80px; height:80px; border-radius:50%; background:rgba(255,255,255,0.08); display:flex; align-items:center; justify-content:center; font-size:2rem; color:#94afcf; }
        @media (max-width:600px) { .profile-container { padding:10px; } }
    </style>
</head>
<body>
    <div class="profile-container">
        <a href="/" class="back-link">← На главную</a>
        <div id="authRequired" style="display:none;">
            <h2>Войдите в профиль</h2>
            <p style="color:#94afcf;">Чтобы управлять гаражом, <a href="/login">войдите</a> или <a href="/register">зарегистрируйтесь</a></p>
        </div>
        <div id="profileContent" style="display:none;">
            <div class="card" style="display:flex; align-items:center; gap:16px;">
                <div id="avatarWrap" style="position:relative; cursor:pointer;" onclick="document.getElementById('avatarInput').click()"></div>
                <input type="file" id="avatarInput" accept="image/*" style="display:none;">
                <div style="flex:1;">
                    <h2 id="profileName" style="margin:0 0 4px 0;"></h2>
                    <div id="profileEmail" style="font-size:0.85rem; color:#94afcf;"></div>
                    <div style="font-size:0.75rem; color:#556677; margin-top:4px;">Нажми на аватар, чтобы изменить</div>
                </div>
            </div>

            <div class="card">
                <h2>🚲 Мой гараж</h2>
                <div id="bikeList"></div>
                <div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
                    <div style="font-size:0.85rem; color:#94afcf; margin-bottom:8px;">Рассчитать давление в шинах:</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <a href="https://axs.sram.com/tirepressureguide" target="_blank" style="flex:1; text-align:center; padding:12px; background:#fa0; color:#000; border-radius:10px; text-decoration:none; font-weight:700; min-width:100px;">SRAM</a>
                        <a href="https://int.vittoria.com/pages/tire-pressure" target="_blank" style="flex:1; text-align:center; padding:12px; background:#e74c3c; color:#fff; border-radius:10px; text-decoration:none; font-weight:600; min-width:100px;">Vittoria</a>
                        <a href="https://www.schwalbe.com/pressureprof/" target="_blank" style="flex:1; text-align:center; padding:12px; background:#3498db; color:#fff; border-radius:10px; text-decoration:none; font-weight:600; min-width:100px;">Schwalbe</a>
                    </div>
                </div>
                <button class="btn btn-primary" id="addBikeBtn" style="margin-top:8px;">+ Добавить байк</button>
                <div id="bikeForm">
                    <h3 id="bikeFormTitle" style="font-size:1rem; color:#eef5ff; margin-bottom:8px;">Новый байк</h3>
                    <label>Название</label>
                    <input type="text" id="bikeName" placeholder="Например: Kona Process 134">
                    <label>Мой вес (кг)</label>
                    <input type="number" id="bikeWeight" value="75" min="30" max="200">
                    <label>Тип резины</label>
                    <select id="bikeTire">
                        <option value="mtb">MTB (2.2-2.5")</option>
                        <option value="mtb_plus">MTB Plus (2.5-3.0")</option>
                        <option value="gravel">Гравел</option>
                        <option value="road">Шоссе</option>
                    </select>
                    <div style="display:flex; gap:8px;">
                        <button class="btn btn-primary" id="saveBikeBtn">Сохранить</button>
                        <button class="btn btn-danger" id="cancelBikeBtn">Отмена</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>⭐ Избранные парки</h2>
                <div id="favList"></div>
            </div>
        </div>
    </div>
    <script>
        const TOKEN = localStorage.getItem('token');
        if (!TOKEN) { document.getElementById('authRequired').style.display = 'block'; }
        else {
            document.getElementById('profileContent').style.display = 'block';
            let editingBikeId = null;

            async function loadProfile() {
                const r = await fetch('/api/user/profile', { headers: { 'Authorization': 'Bearer ' + TOKEN } });
                if (!r.ok) { localStorage.removeItem('token'); location.reload(); return; }
                const p = await r.json();
                document.getElementById('profileName').textContent = p.username || 'Пользователь';
                document.getElementById('profileEmail').textContent = p.email;
                const aw = document.getElementById('avatarWrap');
                if (p.avatar) { aw.innerHTML = '<img src="' + p.avatar + '" class="avatar-img">'; }
                else { aw.innerHTML = '<div class="avatar-placeholder">' + (p.username ? p.username[0].toUpperCase() : '?') + '</div>'; }
                renderBikes(p.bikes);
                renderFavorites(p.favorites);
            }

            function renderBikes(bikes) {
                const el = document.getElementById('bikeList');
                if (!bikes.length) { el.innerHTML = '<div style="color:#556677; font-size:0.9rem;">Нет байков. Добавьте свой велосипед!</div>'; return; }
                el.innerHTML = bikes.map(b => `
                    <div class="bike-item">
                        ${b.photo ? '<img src="'+b.photo+'" style="width:50px;height:50px;border-radius:8px;object-fit:cover;">' : '<div style="width:50px;height:50px;border-radius:8px;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;font-size:1.2rem;color:#556677;">🚲</div>'}
                        <div class="info">
                            <div class="name">${b.name}</div>
                            <div class="detail">${b.rider_weight_kg} кг · ${b.tire_type}</div>
                        </div>
                        <button class="btn btn-sm" style="background:rgba(255,255,255,0.08);color:#94afcf;" onclick="document.getElementById('bikePhotoInput_${b.id}').click()">📷</button>
                        <input type="file" id="bikePhotoInput_${b.id}" accept="image/*" style="display:none;" onchange="uploadBikePhoto(${b.id}, this)">
                        <button class="btn btn-danger btn-sm" onclick="deleteBike(${b.id})">✕</button>
                    </div>
                `).join('');
            }

            function renderFavorites(favs) {
                document.getElementById('favList').innerHTML = favs.length
                    ? favs.map(f => '<span class="fav-item"><a href="/park/' + f.id + '" style="color:#eef5ff;text-decoration:none;">' + (f.name || f.id) + '</a></span>').join('')
                    : '<div style="color:#556677; font-size:0.9rem;">Нет избранных парков</div>';
            }

            document.getElementById('addBikeBtn').addEventListener('click', () => {
                editingBikeId = null;
                document.getElementById('bikeFormTitle').textContent = 'Новый байк';
                document.getElementById('bikeName').value = '';
                document.getElementById('bikeWeight').value = '75';
                document.getElementById('bikeForm').style.display = 'block';
            });

            document.getElementById('cancelBikeBtn').addEventListener('click', () => {
                document.getElementById('bikeForm').style.display = 'none';
            });

            document.getElementById('saveBikeBtn').addEventListener('click', async () => {
                const name = document.getElementById('bikeName').value.trim();
                if (!name) return alert('Введите название');
                const body = { name, rider_weight_kg: parseFloat(document.getElementById('bikeWeight').value), tire_type: document.getElementById('bikeTire').value };
                const url = editingBikeId ? '/api/user/bikes/' + editingBikeId : '/api/user/bikes';
                const method = editingBikeId ? 'PUT' : 'POST';
                const r = await fetch(url, { method, headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                if (r.ok) { document.getElementById('bikeForm').style.display = 'none'; loadProfile(); }
                else { alert('Ошибка сохранения'); }
            });

            window.deleteBike = async (id) => {
                if (!confirm('Удалить байк?')) return;
                const r = await fetch('/api/user/bikes/' + id, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + TOKEN } });
                if (r.ok) loadProfile();
            };

            window.uploadBikePhoto = async (id, input) => {
                const file = input.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const r = await fetch('/api/user/bikes/' + id + '/photo', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ file: e.target.result, name: file.name })
                    });
                    if (r.ok) loadProfile();
                };
                reader.readAsDataURL(file);
            };

            // Avatar upload
            document.getElementById('avatarInput').addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = async (ev) => {
                    const r = await fetch('/api/user/avatar', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ file: ev.target.result, name: file.name })
                    });
                    if (r.ok) loadProfile();
                };
                reader.readAsDataURL(file);
            });

            loadProfile();
        }
    </script>
</body>
</html>
"""

@app.get("/profile", response_class=HTMLResponse)
async def profile_page():
    return HTMLResponse(content=PROFILE_HTML)

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