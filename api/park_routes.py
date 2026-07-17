from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from database.crud import get_park
from database.connection import get_connection
from datetime import datetime, timedelta, timezone
from services.penman_monteith import calc_pm_evaporation
from services.soil_calculator import get_soil_status
from api.dependencies import get_current_user
import os as _os, uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ===== ФУНКЦИЯ ДЛЯ ОПРЕДЕЛЕНИЯ ВРЕМЕНИ СБРОСА (4:00 МСК) =====
def get_reset_time_msk():
    now_msk = datetime.now(timezone.utc) + timedelta(hours=3)
    if now_msk.hour >= 4:
        reset_msk = now_msk.replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        reset_msk = (now_msk - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    reset_utc = reset_msk - timedelta(hours=3)
    return reset_utc

SURFACE_PARAMS = {
    "asphalt": {"z0m": 0.001, "d": 0, "r_s": 0},
    "sand": {"z0m": 0.005, "d": 0, "r_s": 70},
    "loam": {"z0m": 0.015, "d": 0.1, "r_s": 200},
    "clay": {"z0m": 0.015, "d": 0.1, "r_s": 150},
    "clay_heavy": {"z0m": 0.5, "d": 1.5, "r_s": 300},
    "chernozem": {"z0m": 0.015, "d": 0.1, "r_s": 100},
}

def _parse_time(t):
    if isinstance(t, datetime):
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except:
        dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _to_msk(t):
    dt = _parse_time(t)
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%Y-%m-%dT%H:%M")

def _weather_code(temp, rain):
    if rain and rain > 2:
        return 63
    elif rain and rain > 0.5:
        return 61
    elif rain and rain > 0:
        return 80
    elif temp and temp > 25:
        return 1
    elif temp and temp > 15:
        return 2
    else:
        return 3

# ===== ПОЛНЫЙ HTML-ШАБЛОН СТРАНИЦЫ ПАРКА =====
PARK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ park_name }} — МТБ Парки 2.0</title>
    <link rel="stylesheet" href="/css/style.css">
    <style>
        .park-container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .back-link { margin-bottom: 20px; display: inline-block; color: #74a8e2; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .chart-box { margin: 30px 0; max-width: 100%; background: rgba(18,22,30,0.85); border: 1px solid rgba(74,144,226,0.25); border-radius: 12px; padding: 15px; }
        .chart-box canvas { max-height: 300px; }
        .status-badge { font-size: 24px; font-weight: bold; margin: 20px 0; }
        .timer { font-size: 18px; color: #ccc; }
        .route-btn {
            display: inline-block;
            padding: 12px 24px;
            background: #4caf50;
            color: white;
            text-decoration: none;
            border-radius: 28px;
            font-weight: bold;
            margin-top: 15px;
            margin-right: 10px;
        }
        .route-btn:hover { opacity: 0.9; }

        @media (max-width: 600px) {
            .park-container { padding: 10px; }
            .chart-box { padding: 10px; margin: 20px 0; }
            .chart-box canvas { max-height: 250px; }
            .route-btn {
                display: block;
                width: 100%;
                text-align: center;
                margin-right: 0;
                margin-bottom: 10px;
                box-sizing: border-box;
            }
            .status-badge { font-size: 20px; }
            .timer { font-size: 16px; }
            h1 { font-size: 24px; }
            h2 { font-size: 20px; }
            #photoForm {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            #photoForm input[type="file"] {
                width: 100%;
                font-size: 16px;
            }
            #photoForm button {
                width: 100%;
                padding: 14px;
                font-size: 16px;
            }
            #photoGallery {
                grid-template-columns: 1fr 1fr !important;
            }
            .vote-btn {
                flex: 1 0 45% !important;
                font-size: 12px !important;
                padding: 8px 6px !important;
            }
        }

        @media (max-width: 400px) {
            .chart-box canvas { max-height: 220px; }
            h1 { font-size: 22px; }
            .status-badge { font-size: 18px; }
            .vote-btn {
                flex: 1 0 100% !important;
            }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
</head>
<body>
    <div class="park-container">
        <a href="/" class="back-link">← Назад к списку</a>
        <h1>{{ park_name }}</h1>
        <p>Координаты: {{ lat }}, {{ lon }}</p>
        <p>Описание: {{ description }}</p>
        <p>Количество трасс: {{ trails_count }}</p>

        <a href="https://yandex.ru/maps/?rtext=~{{ lat }},{{ lon }}&rtt=auto"
           target="_blank" class="route-btn">🗺️ Проложить маршрут (Яндекс)</a>

        <div class="status-badge" id="soilStatus">Загрузка...</div>
        <div class="timer" id="dryTimer"></div>
        <div id="voteAvg"></div>

        <div class="chart-box">
            <h2>Температура за 7 дней</h2>
            <canvas id="tempChart"></canvas>
        </div>
        <div class="chart-box">
            <h2>Осадки за 7 дней</h2>
            <canvas id="rainChart"></canvas>
        </div>

        <div style="margin-top:20px;">
            <h3>📸 Фотографии грунта</h3>
            <div id="photoUploadArea">
                <div id="authMessage" style="display:none; color:#ff6b6b; padding:10px; background:rgba(255,0,0,0.1); border-radius:8px; margin-bottom:10px;">
                    ⚠️ <a href="/login" style="color:#74a8e2;">Войдите</a>, чтобы загружать фото
                </div>
                <form id="photoForm" enctype="multipart/form-data" style="display:none;">
                    <div style="margin-bottom:10px;">
                        <label style="display:block; margin-bottom:5px; font-weight:600;">Оцените состояние грунта:</label>
                        <div id="voteButtons" style="display:flex; gap:8px; flex-wrap:wrap; justify-content:center;">
                            <button type="button" class="vote-btn" data-vote="1" style="padding:10px 14px; border:2px solid #555; border-radius:12px; background:transparent; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🌿 Болото
                            </button>
                            <button type="button" class="vote-btn" data-vote="2" style="padding:10px 14px; border:2px solid #555; border-radius:12px; background:transparent; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                💧 Мокро
                            </button>
                            <button type="button" class="vote-btn" data-vote="3" style="padding:10px 14px; border:2px solid #555; border-radius:12px; background:transparent; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🌵 Альденте
                            </button>
                            <button type="button" class="vote-btn" data-vote="4" style="padding:10px 14px; border:2px solid #555; border-radius:12px; background:transparent; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                ✅ Сухо
                            </button>
                            <button type="button" class="vote-btn" data-vote="5" style="padding:10px 14px; border:2px solid #555; border-radius:12px; background:transparent; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🪨 Бетон
                            </button>
                        </div>
                        <input type="hidden" id="selectedVote" value="">
                    </div>
                    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
                        <input type="file" id="photoFile" name="file" accept="image/*" style="flex:1; padding:8px; border:1px solid #555; border-radius:8px; background:#1a1e2b; color:white;">
                        <button type="submit" id="photoSubmitBtn" style="padding:12px 24px; background:#4caf50; color:white; border:none; border-radius:28px; font-weight:bold; cursor:pointer;">📤 Загрузить</button>
                    </div>
                    <div style="margin-top:8px;">
                        <textarea id="photoComment" name="comment" placeholder="💬 Комментарий (необязательно)" style="width:100%; box-sizing:border-box; padding:8px; border:1px solid #555; border-radius:8px; background:#1a1e2b; color:white; font-family:inherit; font-size:13px; resize:vertical; min-height:40px; max-height:80px;"></textarea>
                    </div>
                    <div id="uploadStatus" style="margin-top:8px; font-size:14px;"></div>
                </form>
            </div>
            <div id="photoGallery" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:15px; margin-top:15px;"></div>
        </div>

        <div id="park-content">Загрузка данных...</div>
    </div>

    <div id="lightbox" onclick="document.getElementById('lightbox').style.display='none'" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.92); z-index:9999; cursor:pointer; justify-content:center; align-items:center;">
        <img id="lightboxImg" src="" style="max-width:95%; max-height:95%; object-fit:contain; border-radius:8px;">
    </div>

    <script src="/js/park.js"></script>
</body>
</html>
"""

@router.get("/park/{park_id}", response_class=HTMLResponse)
async def park_page(park_id: str):
    park = get_park(park_id)
    if not park:
        return HTMLResponse("<h1>Парк не найден</h1>", status_code=404)
    html = PARK_HTML_TEMPLATE.replace("{{ park_name }}", park.get("name", ""))
    html = html.replace("{{ lat }}", str(park.get("lat", "")))
    html = html.replace("{{ lon }}", str(park.get("lon", "")))
    html = html.replace("{{ description }}", park.get("description") or "Описание пока не добавлено")
    html = html.replace("{{ trails_count }}", str(park.get("trails_count") or "—"))
    return html

@router.get("/api/park/{park_id}/weather")
async def get_park_weather(park_id: str, days: int = Query(7, ge=1, le=30)):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    conn = get_connection()
    try:
        moscow_tz = timezone(timedelta(hours=3))
        today = datetime.now(moscow_tz).date()
        result_days = []
        for i in range(7, 0, -1):
            target_date = (today - timedelta(days=i)).isoformat()
            result_days.append({"date": target_date, "temp_max": None, "rain_total": 0.0})
        since = (today - timedelta(days=7)).isoformat()
        until = (today - timedelta(days=1)).isoformat()
        rows = conn.execute("""
            SELECT date, temperature_max, rain_sum
            FROM weather_daily
            WHERE park_id = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (park_id, since, until)).fetchall()
        for row in rows:
            day_str = row["date"]
            for d in result_days:
                if d["date"] == day_str:
                    d["temp_max"] = row["temperature_max"]
                    d["rain_total"] = row["rain_sum"] or 0.0
                    break
        return {"park_id": park_id, "weather": result_days}
    finally:
        conn.close()

@router.get("/api/park/{park_id}/status")
async def get_park_status(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status as calc_status
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM weather_hourly
            WHERE park_id = ?
            ORDER BY timestamp ASC
        """, (park_id,)).fetchall()
        all_data = [dict(r) for r in rows]
        if not all_data:
            return {"status": "Нет данных", "dryHours": 0, "moisture": 0}
        moisture = calculate_soil_moisture_from_db(park, all_data)
        now_utc = datetime.now(timezone.utc)
        is_asphalt = park.get("soil_type") == "asphalt"
        status = calc_status(moisture["total_rain"], moisture["dry_hours"], moisture["hours_since_rain"], is_asphalt)
        dry_target = None
        if moisture["dry_hours"] > 0:
            dry_target = (now_utc + timedelta(hours=moisture["dry_hours"])).timestamp() * 1000
        return {
            "status": status,
            "dryHours": moisture["dry_hours"],
            "moisture": moisture["current_moisture"],
            "dryTarget": dry_target
        }
    finally:
        conn.close()

# ===== ИСПРАВЛЕННЫЙ ЭНДПОИНТ С КОРРЕКТНЫМ СРАВНЕНИЕМ ДАТ =====
@router.get("/api/park/{park_id}/votes-history")
async def get_park_votes_history(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    conn = get_connection()
    try:
        reset_time_utc = get_reset_time_msk()
        reset_time_str = reset_time_utc.strftime("%Y-%m-%d %H:%M:%S")
        rain_period_start = (reset_time_utc - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        # Проверяем дождь в период перед сбросом
        rain_rows = conn.execute("""
            SELECT COUNT(*) as cnt FROM weather_hourly
            WHERE park_id = ? AND rain > 0
              AND datetime(timestamp) >= datetime(?) AND datetime(timestamp) < datetime(?)
        """, (park_id, rain_period_start, reset_time_str)).fetchone()

        rain_reset = False
        avg = None
        count = 0

        if rain_rows and rain_rows["cnt"] > 0:
            rain_reset = True
            row = conn.execute("""
                SELECT AVG(vote) as avg, COUNT(*) as cnt
                FROM park_photos
                WHERE park_id = ? AND status = 'approved' AND datetime(created_at) > datetime(?)
            """, (park_id, reset_time_str)).fetchone()
            if row and row["cnt"] > 0:
                avg = round(row["avg"], 2)
                count = row["cnt"]
            else:
                avg = None
                count = 0
        else:
            row = conn.execute("""
                SELECT AVG(vote) as avg, COUNT(*) as cnt
                FROM park_photos
                WHERE park_id = ? AND status = 'approved'
            """, (park_id,)).fetchone()
            avg = round(row["avg"], 2) if row["avg"] is not None else None
            count = row["cnt"] or 0

        return {
            "park_id": park_id,
            "avg": avg,
            "count": count,
            "rain_reset": rain_reset
        }
    except Exception as e:
        logger.error(f"Ошибка в votes-history для {park_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        conn.close()

@router.post("/api/park/{park_id}/photos")
async def upload_park_photo(park_id: str, request: Request, user=Depends(get_current_user)):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    form = await request.form()
    file = form.get("file")
    vote_str = form.get("vote")
    comment = form.get("comment", "").strip()
    if not file:
        return JSONResponse({"error": "Файл не найден"}, status_code=400)
    if not vote_str:
        return JSONResponse({"error": "Оценка не указана"}, status_code=400)
    try:
        vote = int(vote_str)
        if vote < 1 or vote > 5:
            raise ValueError
    except ValueError:
        return JSONResponse({"error": "Оценка должна быть числом от 1 до 5"}, status_code=400)
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    filepath = _os.path.join(base_dir, "data", "photos", park_id, filename)
    _os.makedirs(_os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    user_id = user["user_id"]
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO park_photos (park_id, user_id, filename, original_name, vote, comment, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (park_id, user_id, filename, file.filename, vote, comment)
        )
        conn.execute(
            "UPDATE users SET photo_votes_count = photo_votes_count + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        photo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"Фото {filename} сохранено, id={photo_id}, vote={vote}, comment={comment!r}, user_id={user_id}")
    finally:
        conn.close()
    return {"ok": True, "filename": filename, "vote": vote, "comment": comment, "photo_id": photo_id}

@router.get("/api/park/{park_id}/photos")
async def get_park_photos(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT p.id, p.filename, p.original_name, p.created_at, p.vote, p.comment, u.username
            FROM park_photos p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.park_id = ? AND p.status = 'approved'
            ORDER BY p.created_at DESC
            LIMIT 20
        """, (park_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()