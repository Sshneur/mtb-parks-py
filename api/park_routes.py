from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from database.crud import get_park
from database.connection import get_connection
from datetime import datetime, timedelta, timezone
from services.penman_monteith import calc_pm_evaporation
from services.soil_calculator import get_soil_status
import os as _os, uuid, asyncio

router = APIRouter()

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

        /* ---------- Адаптация для мобильных ---------- */
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
                justify-content: space-between;
            }
            #photoGallery img {
                width: calc(50% - 5px);  /* две колонки с отступом */
                height: auto;
                aspect-ratio: 1 / 1;
                object-fit: cover;
            }
        }

        @media (max-width: 400px) {
            .chart-box canvas { max-height: 220px; }
            h1 { font-size: 22px; }
            .status-badge { font-size: 18px; }
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
            <h3>Фотографии грунта</h3>
            <form id="photoForm" enctype="multipart/form-data">
                <input type="file" id="photoFile" name="file" accept="image/*">
                <button type="submit">Загрузить фото</button>
            </form>
            <div id="photoGallery" style="display:flex; flex-wrap:wrap; gap:10px; margin-top:10px;"></div>
        </div>

        <div id="park-content">Загрузка данных...</div>
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
    """Возвращает агрегированные по дням данные температуры (max) и осадков (сумма) из weather_daily."""
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    conn = get_connection()
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT date, temperature_max, rain_sum
            FROM weather_daily
            WHERE park_id = ? AND date >= ?
            ORDER BY date ASC
        """, (park_id, since)).fetchall()

        # Формируем массив ровно из 7 элементов
        result_days = []
        today = datetime.now(timezone.utc).date()
        for i in range(days - 1, -1, -1):
            target_date = (today - timedelta(days=i)).isoformat()
            result_days.append({
                "date": target_date,
                "temp_max": None,
                "rain_total": 0.0
            })

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

        now_utc = datetime.now(timezone.utc)
        soil_type = park.get("soil_type", "loam")
        surf = SURFACE_PARAMS.get(soil_type, SURFACE_PARAMS["loam"])
        forest_coef = park.get("forest_coef", 0.3)

        W = 0.0
        last_rain_time = None
        total_rain = 0.0
        recent_evaps = []

        for hour in all_data:
            timestamp = _parse_time(hour["timestamp"])
            temp = hour.get("temperature") or 15
            wind = hour.get("wind_speed") or 0
            rad = hour.get("radiation") or 0
            rain = hour.get("rain") or 0
            rel_hum = hour.get("relative_humidity")
            press = hour.get("surface_pressure")

            if rain > 0:
                W = min(1.0, W + rain / 10)
                total_rain += rain
                last_rain_time = timestamp
            else:
                if rel_hum is None: rel_hum = 70.0
                if press is None: press = 1013.0
                evap = calc_pm_evaporation(
                    temp_c=temp, wind_speed=wind, radiation=rad,
                    relative_humidity=rel_hum, pressure_pa=press * 100,
                    z0m=surf["z0m"], d=surf["d"], r_s=surf["r_s"]
                ) * forest_coef
                W = max(0.0, W - evap / 10)
                if (now_utc - timestamp).total_seconds() <= 86400:
                    recent_evaps.append(evap)

        if recent_evaps:
            last_evap = sum(recent_evaps) / len(recent_evaps)
        else:
            last_evap = 0.001

        dry_hours = W / (last_evap / 10) if last_evap > 0 else 0
        dry_target = None
        if dry_hours > 0:
            dry_target = (now_utc + timedelta(hours=dry_hours)).timestamp() * 1000

        hours_since_rain = (now_utc - last_rain_time).total_seconds() / 3600 if last_rain_time else None
        status = get_soil_status(total_rain, dry_hours, hours_since_rain, soil_type == "asphalt")

        return {
            "status": status,
            "dryHours": round(dry_hours, 1),
            "moisture": round(W, 3),
            "dryTarget": dry_target,
            "rain_total": round(total_rain, 1)
        }
    finally:
        conn.close()

@router.get("/api/park/{park_id}/votes-history")
async def get_park_votes_history(park_id: str, days: int = Query(30, ge=1, le=90)):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    conn = get_connection()
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT DATE(created_at) as day, AVG(vote) as avg, COUNT(*) as cnt
            FROM votes_history
            WHERE park_id = ? AND DATE(created_at) >= ?
            GROUP BY day
            ORDER BY day ASC
        """, (park_id, since)).fetchall()

        history = []
        for row in rows:
            history.append({
                "date": row["day"],
                "avg": round(row["avg"], 2),
                "count": row["cnt"]
            })
        return {"park_id": park_id, "history": history}
    finally:
        conn.close()

@router.post("/api/park/{park_id}/photos")
async def upload_park_photo(park_id: str, request: Request):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    from fastapi import UploadFile, File
    form = await request.form()
    file = form.get("file")
    if not file:
        return JSONResponse({"error": "Файл не найден"}, status_code=400)

    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    filepath = _os.path.join(base_dir, "data", "photos", park_id, filename)
    _os.makedirs(_os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "wb") as f:
        f.write(await file.read())

    # Временно ставим user_id = 1 (админ) для теста
    user_id = 1
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO park_photos (park_id, user_id, filename, original_name, status) VALUES (?, ?, ?, ?, 'pending')",
            (park_id, user_id, filename, file.filename)
        )
        conn.commit()
        photo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"Фото {filename} сохранено, id={photo_id}")
    finally:
        conn.close()

    return {"ok": True, "filename": filename}

@router.get("/api/park/{park_id}/photos")
async def get_park_photos(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT p.id, p.filename, p.original_name, p.created_at, u.username
            FROM park_photos p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.park_id = ? AND p.status = 'approved'
            ORDER BY p.created_at DESC
            LIMIT 20
        """, (park_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()