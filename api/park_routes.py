from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from database.crud import get_park, get_all_parks
from database.connection import get_connection
from datetime import datetime, timedelta, timezone
from services.soil_calculator import get_soil_status, calculate_soil_moisture_from_db
from api.dependencies import get_current_user
from api.utils import parse_time, to_msk, weather_code, MOSCOW_TZ
import os as _os, uuid
import html as _html
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

# ===== HTML-ШАБЛОН СТРАНИЦЫ КАЛЕНДАРЯ =====
CALENDAR_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ park_name }} — Календарь зелёных дней</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <script>
    (function(){
        var s = localStorage.getItem('theme');
        if (s === 'light' || (!s && window.matchMedia('(prefers-color-scheme:light)').matches)) document.documentElement.classList.add('theme-light');
    })();
    </script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg-end); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { font-size: 1.5rem; margin-bottom: 4px; }
        .subtitle { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 20px; }
        .nav { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 20px; }
        .nav button { background: rgba(74,144,226,0.15); border: 1px solid rgba(74,144,226,0.3); color: #74a8e2; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-size: 1rem; }
        .nav button:hover { background: rgba(74,144,226,0.25); }
        .nav .month-label { font-size: 1.1rem; font-weight: 600; min-width: 120px; text-align: center; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; max-width: 350px; margin: 0 auto; }
        .day-cell { aspect-ratio: 1; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; cursor: pointer; position: relative; transition: transform 0.15s; }
        .day-cell:hover { transform: scale(1.15); }
        .day-cell.today { outline: 2px solid #f0c000; outline-offset: -2px; }
        .day-cell.dry { background: #1a7f37; }
        .day-cell.wet { background: #1f6feb; }
        .day-cell.bog { background: #8b5e3c; }
        .day-cell.no_data { background: #21262d; }
        .day-header { color: #8b949e; font-size: 0.7rem; text-align: center; padding: 4px 0; }
        .legend { display: flex; justify-content: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #8b949e; }
        .legend-swatch { width: 12px; height: 12px; border-radius: 3px; }
        .tooltip { position: fixed; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; font-size: 0.85rem; z-index: 100; box-shadow: 0 4px 20px rgba(0,0,0,0.4); max-width: 220px; display: none; }
        .tooltip .date { font-weight: 600; margin-bottom: 4px; }
        .tooltip .status { margin-top: 2px; }
        .back-link { display: inline-block; margin-bottom: 16px; color: var(--accent); text-decoration: none; font-size: 0.9rem; }
        .back-link:hover { text-decoration: underline; }
        #loading { text-align: center; padding: 40px; color: var(--text-muted); }
        @media (max-width: 400px) {
            .calendar-grid { max-width: 280px; gap: 3px; }
            .day-cell { font-size: 0.6rem; }
        }
    </style>
</head>
<body>
    <div class="container" style="position:relative;">
        <button id="calendarThemeToggle" style="position:absolute; top:0; right:0; background:none; border:none; font-size:1.3rem; cursor:pointer; padding:4px 8px; line-height:1; color:var(--text);">🌙</button>
        <a href="/park/{{ park_id }}" class="back-link">← {{ park_name }}</a>
        <h1>📅 Календарь зелёных дней</h1>
        <div class="subtitle">Состояние грунта на 23:00 МСК по дням</div>

        <div class="nav">
            <button id="prevMonth">←</button>
            <span class="month-label" id="monthLabel"></span>
            <button id="nextMonth">→</button>
        </div>

        <div id="loading">Загрузка...</div>

        <div id="calendarWrap" style="display:none;">
            <div class="calendar-grid" id="calendarGrid">
                <div class="day-header">Пн</div>
                <div class="day-header">Вт</div>
                <div class="day-header">Ср</div>
                <div class="day-header">Чт</div>
                <div class="day-header">Пт</div>
                <div class="day-header">Сб</div>
                <div class="day-header">Вс</div>
            </div>

            <div class="legend">
                <div class="legend-item"><div class="legend-swatch" style="background:#1a7f37;"></div> Сухо</div>
                <div class="legend-item"><div class="legend-swatch" style="background:#1f6feb;"></div> Мокро</div>
                <div class="legend-item"><div class="legend-swatch" style="background:#8b5e3c;"></div> Болото</div>
                <div class="legend-item"><div class="legend-swatch" style="background:#21262d;"></div> Нет данных</div>
            </div>
        </div>

        <div class="tooltip" id="tooltip"></div>
    </div>

    <script>
    const parkId = "{{ park_id }}";
    const today = new Date();
    let currentYear = today.getFullYear();
    let currentMonth = today.getMonth();
    const monthNames = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Окторябрь","Ноябрь","Декабрь"];

    function pad2(n) { return n.toString().padStart(2, '0'); }

    function loadMonth(year, month) {
        const monthStr = year + '-' + pad2(month + 1);
        document.getElementById('monthLabel').textContent = monthNames[month] + ' ' + year;
        document.getElementById('loading').style.display = 'block';
        document.getElementById('calendarWrap').style.display = 'none';

        fetch('/api/park/' + parkId + '/green-days?month=' + monthStr)
            .then(r => r.json())
            .then(data => {
                renderCalendar(data, year, month);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('calendarWrap').style.display = 'block';
            })
            .catch(err => {
                document.getElementById('loading').textContent = 'Ошибка загрузки';
            });
    }

    function renderCalendar(data, year, month) {
        const grid = document.getElementById('calendarGrid');
        const headers = grid.querySelectorAll('.day-header');
        grid.innerHTML = '';
        headers.forEach(h => grid.appendChild(h.cloneNode(true)));

        const days = data.days || [];
        const dayMap = {};
        days.forEach(d => { dayMap[d.date] = d; });

        const firstDay = new Date(year, month, 1);
        let startDow = firstDay.getDay();
        startDow = startDow === 0 ? 6 : startDow - 1;

        for (let i = 0; i < startDow; i++) {
            const empty = document.createElement('div');
            empty.className = 'day-cell';
            empty.style.visibility = 'hidden';
            grid.appendChild(empty);
        }

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const todayStr = today.getFullYear() + '-' + pad2(today.getMonth() + 1) + '-' + pad2(today.getDate());

        for (let d = 1; d <= daysInMonth; d++) {
            const key = year + '-' + pad2(month + 1) + '-' + pad2(d);
            const dayData = dayMap[key];
            const cell = document.createElement('div');
            cell.className = 'day-cell';
            if (key === todayStr) cell.classList.add('today');
            if (!dayData || dayData.status === 'no_data') {
                cell.classList.add('no_data');
                cell.textContent = d;
            } else {
                cell.classList.add(dayData.status);
                cell.textContent = d;
            }
            cell.dataset.key = key;
            cell.addEventListener('click', function(e) { showTooltip(e, dayData, key); });
            grid.appendChild(cell);
        }
    }

    function showTooltip(event, dayData, key) {
        const tip = document.getElementById('tooltip');
        const dateStr = key.split('-').reverse().join('.');
        let html = '<div class="date">' + dateStr + '</div>';
        if (!dayData || dayData.status === 'no_data') {
            html += '<div class="status">Нет данных</div>';
        } else {
            const labels = { dry: 'Сухо ✅', wet: 'Мокро 💧', bog: 'Болото 🟤' };
            html += '<div class="status">' + (labels[dayData.status] || dayData.label) + '</div>';
            if (dayData.W !== null && dayData.W !== undefined) {
                html += '<div style="font-size:0.75rem; color:#8b949e; margin-top:2px;">W = ' + dayData.W.toFixed(3) + '</div>';
            }
        }
        tip.innerHTML = html;
        tip.style.display = 'block';
        let x = event.clientX + 12;
        let y = event.clientY + 8;
        if (x + 230 > window.innerWidth) x = event.clientX - 230;
        if (y + 100 > window.innerHeight) y = event.clientY - 100;
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
    }

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.day-cell')) {
            document.getElementById('tooltip').style.display = 'none';
        }
    });

    document.getElementById('prevMonth').addEventListener('click', function() {
        currentMonth--;
        if (currentMonth < 0) { currentMonth = 11; currentYear--; }
        loadMonth(currentYear, currentMonth);
    });

    document.getElementById('nextMonth').addEventListener('click', function() {
        currentMonth++;
        if (currentMonth > 11) { currentMonth = 0; currentYear++; }
        loadMonth(currentYear, currentMonth);
    });

    loadMonth(currentYear, currentMonth);

    // theme toggle
    var ctBtn = document.getElementById('calendarThemeToggle');
    if (ctBtn) {
        ctBtn.textContent = document.documentElement.classList.contains('theme-light') ? '☀️' : '🌙';
        ctBtn.addEventListener('click', function() {
            document.documentElement.classList.toggle('theme-light');
            var isLight = document.documentElement.classList.contains('theme-light');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            ctBtn.textContent = isLight ? '☀️' : '🌙';
        });
    }
    </script>
</body>
</html>"""

PARK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>{{ park_name }} — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <meta name="description" content="Состояние грунта на трассах {{ park_name }}: сухо, мокро, болото или бетон. Прогноз погоды, фото грунта, оценки райдеров.">
    <meta property="og:title" content="{{ park_name }} — Что с грунтом?">
    <meta property="og:description" content="Проверь состояние грунта в {{ park_name }}. Прогноз погоды, фото, оценки райдеров.">
    <meta property="og:image" content="https://gripcheck.ru/og-image.jpg">
    <meta property="og:image:secure_url" content="https://gripcheck.ru/og-image.jpg">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:url" content="https://gripcheck.ru/park/{{ park_id }}">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="ru_RU">
    <style>
        .park-container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .back-link { margin-bottom: 20px; display: inline-block; color: var(--accent); text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .chart-box { margin: 20px 0; max-width: 100%; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 14px; padding: 14px; }
        .chart-box canvas { max-height: 220px; width: 100% !important; }
        .timer { font-size: 18px; color: var(--text-muted); }
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
            #statusCard { padding: 12px !important; }
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
            #statusCard { padding: 10px !important; }
            #soilStatus { font-size: 22px !important; }
            .vote-btn {
                flex: 1 0 100% !important;
            }
        }
    </style>
    <script>
    (function(){
        var s = localStorage.getItem('theme');
        if (s === 'light' || (!s && window.matchMedia('(prefers-color-scheme:light)').matches)) document.documentElement.classList.add('theme-light');
    })();
    </script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
</head>
<body>
    <div class="park-container" style="position:relative;">
        <button id="parkThemeToggle" style="position:absolute; top:0; right:0; background:none; border:none; font-size:1.3rem; cursor:pointer; padding:4px 8px; line-height:1; color:var(--text);">🌙</button>
        <a href="/" class="back-link">← Назад к списку</a>
        <h1>{{ park_name }}</h1>
        <p>Координаты: {{ lat }}, {{ lon }}</p>
        <p>Описание: {{ description }}</p>
        <p>Количество трасс: {{ trails_count }}</p>

        <a href="https://yandex.ru/maps/?rtext=~{{ lat }},{{ lon }}&rtt=auto"
           target="_blank" class="route-btn">🗺️ Проложить маршрут (Яндекс)</a>

        <div id="statusCard" style="background:var(--card-bg); border:1px solid var(--card-border); border-radius:14px; padding:16px; margin:16px 0; text-align:center;">
            <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:6px;">Состояние грунта по данным погоды</div>
            <div class="status-badge" id="soilStatus" style="font-size:26px; font-weight:700;">Загрузка...</div>
            <div class="timer" id="dryTimer" style="font-size:15px; color:var(--text-muted); margin-top:4px;"></div>
        </div>
        <div id="voteAvg"></div>

        <div class="forecast-box" id="forecastBox" style="display:none;">
            <h2 style="font-size:1.2rem; margin-bottom:10px;">🌤 Прогноз грунта</h2>
            <div id="forecastGrid"></div>
            <div id="forecastBest" style="margin-top:10px; font-size:0.9rem; color:var(--text-muted); text-align:center;"></div>
            <div style="margin-top:6px; font-size:0.75rem; color:var(--text-muted);">
                <a href="/development" style="color:var(--text-muted);">Как это считается?</a>
            </div>
        </div>

        <div style="text-align:center; margin:16px 0;">
            <a href="/park/{{ park_id }}/calendar" style="display:inline-block; padding:10px 20px; background:rgba(74,144,226,0.15); border:1px solid rgba(74,144,226,0.3); border-radius:28px; color:var(--accent); text-decoration:none; font-size:14px;">📅 Календарь зелёных дней</a>
        </div>

        <div class="chart-box">
            <h2 style="font-size:1rem; color:var(--text); margin-bottom:8px;">🌡 Температура за 7 дней</h2>
            <canvas id="tempChart" style="height:200px;"></canvas>
        </div>
        <div class="chart-box">
            <h2 style="font-size:1rem; color:var(--text); margin-bottom:8px;">🌧 Осадки за 7 дней</h2>
            <canvas id="rainChart" style="height:200px;"></canvas>
        </div>

        <div style="margin-top:20px;">
            <h3>📸 Фотографии грунта</h3>
            <div id="photoUploadArea">
                <div id="authMessage" style="display:none; color:#ff6b6b; padding:10px; background:rgba(255,0,0,0.1); border-radius:8px; margin-bottom:10px;">
                    ⚠️ <a href="/login" style="color:var(--accent);">Войдите</a>, чтобы загружать фото
                </div>
                <form id="photoForm" enctype="multipart/form-data" style="display:none;">
                    <div style="margin-bottom:10px;">
                        <label style="display:block; margin-bottom:5px; font-weight:600;">Оцените состояние грунта:</label>
                        <div id="voteButtons" style="display:flex; gap:8px; flex-wrap:wrap; justify-content:center;">
                            <button type="button" class="vote-btn" data-vote="1" style="padding:10px 14px; border:2px solid var(--inline-border); border-radius:12px; background:transparent; color:var(--text); font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🌿 Болото
                            </button>
                            <button type="button" class="vote-btn" data-vote="2" style="padding:10px 14px; border:2px solid var(--inline-border); border-radius:12px; background:transparent; color:var(--text); font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                💧 Мокро
                            </button>
                            <button type="button" class="vote-btn" data-vote="3" style="padding:10px 14px; border:2px solid var(--inline-border); border-radius:12px; background:transparent; color:var(--text); font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🌵 Альденте
                            </button>
                            <button type="button" class="vote-btn" data-vote="4" style="padding:10px 14px; border:2px solid var(--inline-border); border-radius:12px; background:transparent; color:var(--text); font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                ✅ Сухо
                            </button>
                            <button type="button" class="vote-btn" data-vote="5" style="padding:10px 14px; border:2px solid var(--inline-border); border-radius:12px; background:transparent; color:var(--text); font-size:14px; cursor:pointer; transition:all 0.2s; flex:1 0 60px;">
                                🪨 Бетон
                            </button>
                        </div>
                        <input type="hidden" id="selectedVote" value="">
                    </div>
                    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
                        <input type="file" id="photoFile" name="file" accept="image/*" style="flex:1; padding:8px; border:1px solid var(--inline-input-border); border-radius:8px; background:var(--inline-input-bg); color:var(--text);">
                        <button type="submit" id="photoSubmitBtn" style="padding:12px 24px; background:#4caf50; color:white; border:none; border-radius:28px; font-weight:bold; cursor:pointer;">📤 Загрузить</button>
                    </div>
                    <div style="margin-top:8px;">
                        <textarea id="photoComment" name="comment" placeholder="💬 Комментарий (необязательно)" style="width:100%; box-sizing:border-box; padding:8px; border:1px solid var(--inline-input-border); border-radius:8px; background:var(--inline-input-bg); color:var(--text); font-family:inherit; font-size:13px; resize:vertical; min-height:40px; max-height:80px;"></textarea>
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

    <script src="/js/park.js?v=5"></script>
</body>
</html>
"""

MAP_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Карта — Что с грунтом?</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="stylesheet" href="/lib/leaflet.css">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0b0d14">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; overflow: hidden; background: #0b0d14; }
#map { width: 100%; height: 100%; }
.back-btn {
  position: fixed; bottom: 20px; left: 20px; z-index: 1000;
  width: 48px; height: 48px; border-radius: 50%;
  background: rgba(0,0,0,0.75); border: 2px solid rgba(255,255,255,0.2);
  color: #eef5ff; font-size: 22px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
@media (max-width: 700px) {
  .back-btn { bottom: calc(20px + env(safe-area-inset-bottom, 0px)); }
}
</style>
</head>
<body>
<a href="/" class="back-btn">←</a>
<div id="map"></div>
<script src="/lib/leaflet.js"></script>
<script>
(function() {
  var map = L.map('map', { zoomControl: true, attributionControl: false, fadeAnimation: false });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; <a href="https://openstreetmap.org">OSM</a>'
  }).addTo(map);
  map.setView([55.65, 37.49], 10);

  L.control({ position: 'topright' }).onAdd = function() {
    var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
    div.innerHTML = '<a href="#" style="font-size:22px;line-height:44px;display:flex;align-items:center;justify-content:center;" title="Моё местоположение">📍</a>';
    div.onclick = function(e) {
      e.preventDefault();
      if (!navigator.geolocation) { alert('Геолокация не поддерживается'); return; }
      navigator.geolocation.getCurrentPosition(function(pos) {
        map.setView([pos.coords.latitude, pos.coords.longitude], 14);
        L.circleMarker([pos.coords.latitude, pos.coords.longitude], {
          radius: 8, color: '#4a90e2', fillColor: '#4a90e2', fillOpacity: 0.6
        }).addTo(map);
      }, function() { alert('Не удалось определить местоположение'); });
    };
    return div;
  }.bind(this);

  var statusColors = {
    'Бетон': '#ffd700', 'Сухо': '#4caf50', 'Альденте': '#ff9800',
    'Мокро': '#2196f3', 'Болото': '#9c27b0'
  };

  fetch('/api/park/list').then(function(r) { return r.json(); }).then(function(data) {
    data.forEach(function(p) {
      var color = '#666';
      for (var key in statusColors) {
        if (p.soilStatus && p.soilStatus.indexOf(key) >= 0) { color = statusColors[key]; break; }
      }
      L.marker([p.lat, p.lon], {
        icon: L.divIcon({
          html: '<div style="background:' + color + ';width:22px;height:22px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.6);"></div>',
          iconSize: [28, 28], iconAnchor: [14, 14], className: ''
        })
      }).addTo(map).bindPopup(
        '<b><a href="/park/' + p.parkId + '" style="color:#4a90e2;text-decoration:none;">' + p.name + '</a></b><br>' +
        '<span style="font-size:13px;">' + p.soilStatus + '</span>'
      );
    });
  }).catch(function(e) { console.error('loadMap error', e); });

  setTimeout(function() { map.invalidateSize(); }, 50);
})();
</script>
</body>
</html>"""

@router.get("/map", response_class=HTMLResponse)
async def map_page():
    return HTMLResponse(content=MAP_HTML)

@router.get("/park/{park_id}", response_class=HTMLResponse)
async def park_page(park_id: str):
    park = get_park(park_id)
    if not park:
        return HTMLResponse("<h1>Парк не найден</h1>", status_code=404)
    html = PARK_HTML_TEMPLATE.replace("{{ park_name }}", _html.escape(park.get("name", "")))
    html = html.replace("{{ park_id }}", _html.escape(park_id, quote=True))
    html = html.replace("{{ lat }}", _html.escape(str(park.get("lat", ""))))
    html = html.replace("{{ lon }}", _html.escape(str(park.get("lon", ""))))
    html = html.replace("{{ description }}", _html.escape(park.get("description") or "Описание пока не добавлено"))
    html = html.replace("{{ trails_count }}", _html.escape(str(park.get("trails_count") or "—")))
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

@router.get("/api/park/{park_id}/soil-forecast")
async def get_soil_forecast(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    from services.forecast_cache import get_cached_forecast, set_cached_forecast
    cached = get_cached_forecast(park_id)
    if cached:
        return cached

    from services.open_meteo import get_forecast as fetch_forecast
    data = await fetch_forecast(park["lat"], park["lon"])
    if not data or "hourly" not in data:
        return {"forecast": []}

    hourly = data["hourly"]
    times = hourly["time"]
    temps = hourly["temperature_2m"]
    rains = hourly["rain"]
    winds = hourly["wind_speed_10m"]
    hums = hourly.get("relativehumidity_2m", [50]*len(times))

    utc = timezone.utc
    msk = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk)

    # Build hourly data, all in MSK
    hours = []
    for i in range(len(times)):
        ht = parse_time(times[i])  # UTC
        ht_msk = ht.astimezone(msk)
        hours.append({
            "timestamp": ht_msk,
            "temperature": temps[i],
            "rain": rains[i],
            "wind_speed": winds[i],
            "radiation": hourly.get("shortwave_radiation", [0]*len(times))[i],
            "humidity": hums[i],
        })

    from database.models import SOIL_COEFFICIENTS as _SOIL_COEF
    _sc = _SOIL_COEF.get(park.get("soil_type", "loam"), _SOIL_COEF["loam"])
    forest_factor = park.get("forest_coef", 0.3)
    W = park.get("current_moisture", 0.0)

    # Build flat list of all periods (day_offset, period)
    day_dates = [now_msk.date() + timedelta(days=d) for d in range(3)]
    period_defs = [
        {"id": "morning", "label": "Утро", "start": 6, "end": 12},
        {"id": "day", "label": "День", "start": 12, "end": 18},
        {"id": "evening", "label": "Вечер", "start": 18, "end": 0},
    ]
    all_periods = []
    for d in range(3):
        for p in period_defs:
            p_start = datetime(day_dates[d].year, day_dates[d].month, day_dates[d].day, p["start"], tzinfo=msk)
            if p["end"] == 0:
                p_end = p_start.replace(hour=0) + timedelta(days=1)
            else:
                p_end = datetime(day_dates[d].year, day_dates[d].month, day_dates[d].day, p["end"], tzinfo=msk)
            all_periods.append({
                "day_offset": d, "day_date": day_dates[d],
                "period": p, "start": p_start, "end": p_end,
                "hours": [], "rain_sum": 0, "temp_acc": 0, "wind_acc": 0, "count": 0,
                "evap_sum": 0,
            })
    if not all_periods:
        return {"park_id": park_id, "forecast": []}

    # Sort all forecast hours and distribute into periods, tracking W
    hours_sorted = sorted(hours, key=lambda h: h["timestamp"])
    last_evap = 0.001
    for h in hours_sorted:
        is_past = h["timestamp"] < now_msk
        # For past hours: still record weather data, but don't update W
        if not is_past:
            if h["rain"] > 0:
                W = min(1.0, W + h["rain"] / 10)
                last_evap = 0.001
            else:
                fT = 0.05 * max(h["temperature"], 0)
                gv = 0.03 * h["wind_speed"]
                gr = 0.001 * h["radiation"]
                evap = forest_factor * (_sc["k_t"] * fT + _sc["k_w"] * gv + _sc["k_r"] * gr + _sc["k_s"])
                last_evap = max(evap, 0.001)
                W = max(0.0, W - evap)
        # Check if this hour falls in any period
        for ap in all_periods:
            if ap["start"] <= h["timestamp"] < ap["end"]:
                ap["hours"].append({"W": W, "evap": last_evap, "h": h})
                ap["rain_sum"] += h["rain"]
                ap["temp_acc"] += h["temperature"]
                ap["wind_acc"] += h["wind_speed"]
                ap["count"] += 1
                ap["evap_sum"] += last_evap
                break

    # Now build response
    days_names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    day_results = {}
    for d in range(3):
        day_results[d] = {"periods": [], "best": {"confidence": 0}}

    for ap in all_periods:
        d = ap["day_offset"]
        count = ap["count"]
        avg_temp = round(ap["temp_acc"] / count, 1) if count else 0
        avg_wind = round(ap["wind_acc"] / count, 1) if count else 0
        last_W = ap["hours"][-1]["W"] if ap["hours"] else park.get("current_moisture", 0.0)

        # Soil from last hour's W → dry_hours (consistent with get_soil_status)
        evap_rate = park.get("evaporation_rate", 0.001)
        dry_hours = last_W / evap_rate if evap_rate > 0 else last_W / 0.001
        if dry_hours >= 72:
            soil, emoji = "болото", "🟤"
        elif dry_hours > 24:
            soil, emoji = "мокро", "💧"
        elif dry_hours > 0:
            soil, emoji = "альденте", "🌵"
        else:
            soil, emoji = "сухо", "🟢"

        confidence = max(0.3, 0.9 - d * 0.2)
        pdata = {
            "period": ap["period"]["id"], "label": ap["period"]["label"],
            "soil": soil, "emoji": emoji,
            "temp": avg_temp, "wind": avg_wind,
            "rain": round(ap["rain_sum"], 1),
            "confidence": round(confidence, 2),
        }
        day_results[d]["periods"].append(pdata)
        if count > 0 and ap["end"] > now_msk and pdata["confidence"] > day_results[d]["best"]["confidence"] and pdata["soil"] in ("сухо", "альденте"):
            day_results[d]["best"] = pdata

    result = []
    for d in range(3):
        dd = day_results[d]
        day_entry = {
            "date": day_dates[d].isoformat(),
            "day_name": days_names[day_dates[d].weekday()],
            "periods": dd["periods"],
        }
        if dd["best"].get("soil"):
            day_entry["best_period"] = {
                "period": dd["best"]["period"],
                "label": dd["best"]["label"],
                "soil": dd["best"]["soil"],
                "temp": dd["best"]["temp"],
                "reason": f"{dd['best']['label']}, {dd['best']['soil']}, +{dd['best']['temp']}°C"
            }
        result.append(day_entry)

    response = {"park_id": park_id, "forecast": result}
    set_cached_forecast(park_id, response)
    return response


@router.get("/api/park/{park_id}/status")
async def get_park_status(park_id: str):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    from services.soil_calculator import calculate_soil_moisture_from_db, get_soil_status as calc_status
    conn = get_connection()
    try:
        now_utc = datetime.now(timezone.utc)
        rows = conn.execute("""
            SELECT * FROM weather_hourly
            WHERE park_id = ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (park_id, now_utc.isoformat())).fetchall()
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

@router.get("/api/park/list")
async def get_park_list():
    parks = get_all_parks()
    if not parks:
        return []
    results = []
    conn = get_connection()
    now_utc = datetime.now(timezone.utc)
    for park in parks:
        rows = conn.execute("""
            SELECT * FROM weather_hourly
            WHERE park_id = ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (park["id"], now_utc.isoformat())).fetchall()
        all_data = [dict(r) for r in rows]
        if all_data:
            moisture = calculate_soil_moisture_from_db(park, all_data)
            is_asphalt = park.get("soil_type") == "asphalt"
            status = get_soil_status(
                moisture["total_rain"],
                moisture["dry_hours"],
                moisture["hours_since_rain"],
                is_asphalt
            )
        else:
            status = "Нет данных"
        results.append({
            "parkId": park["id"],
            "name": park["name"],
            "lat": park["lat"],
            "lon": park["lon"],
            "soilStatus": status
        })
    conn.close()
    return results

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
        logger.error(f"Ошибка в votes-history для {park_id}: {e}", exc_info=True)
        return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
    finally:
        conn.close()

@router.post("/api/park/{park_id}/photos")
async def upload_park_photo(park_id: str, request: Request, user=Depends(get_current_user)):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    body = await request.json()
    file_data = body.get("file", "")
    original_name = body.get("name", "photo.jpg")
    vote = body.get("vote")
    comment = body.get("comment", "").strip()
    logger.info(f"Upload JSON: file_data_len={len(file_data)}, vote={vote!r}, name={original_name!r}")
    if not vote:
        return JSONResponse({"error": "Оценка не указана"}, status_code=400)
    try:
        vote = int(vote)
        if vote < 1 or vote > 5:
            raise ValueError
    except ValueError:
        return JSONResponse({"error": "Оценка должна быть числом от 1 до 5"}, status_code=400)

    from api.upload_utils import parse_file, check_upload_limit, ALLOWED_EXT

    file_bytes, _, error = parse_file(file_data)
    if error:
        status = 413 if "слишком большой" in error else 400
        return JSONResponse({"error": error}, status_code=status)
    ext = original_name.split('.')[-1].lower() if '.' in original_name else 'jpg'
    if f".{ext}" not in ALLOWED_EXT:
        return JSONResponse({"error": "Недопустимый тип файла"}, status_code=400)

    user_id = user["user_id"]
    if not check_upload_limit(user_id):
        return JSONResponse({"error": "Лимит: не более 10 загрузок в час"}, status_code=429)

    conn = get_connection()
    try:
        recent = conn.execute(
            "SELECT COUNT(*) FROM park_photos WHERE user_id = ? AND created_at > datetime('now', '-1 hour')",
            (user_id,)
        ).fetchone()[0]
        if recent >= 10:
            return JSONResponse({"error": "Лимит: не более 10 фото в час"}, status_code=429)
    finally:
        conn.close()

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    filepath = _os.path.join(base_dir, "data", "photos", park_id, filename)
    _os.makedirs(_os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"Ошибка записи файла {filename}: {e}")
        return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO park_photos (park_id, user_id, filename, original_name, vote, comment, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (park_id, user_id, filename, original_name, vote, comment)
        )
        conn.execute(
            "UPDATE users SET photo_votes_count = photo_votes_count + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        photo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"Фото {filename} сохранено, id={photo_id}, vote={vote}, comment={comment!r}, user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка сохранения фото {filename} в БД: {e}")
        try:
            _os.remove(filepath)
        except OSError:
            pass
        return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
    finally:
        conn.close()
    return {"ok": True, "filename": filename, "vote": vote, "comment": comment, "photo_id": photo_id}

@router.get("/api/park/{park_id}/photos")
async def get_park_photos(park_id: str, limit: int = 10, offset: int = 0):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM park_photos WHERE park_id = ? AND status = 'approved'",
            (park_id,)
        ).fetchone()[0]
        rows = conn.execute("""
            SELECT p.id, p.filename, p.original_name, p.created_at, p.vote, p.comment, u.username
            FROM park_photos p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.park_id = ? AND p.status = 'approved'
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        """, (park_id, limit, offset)).fetchall()
        return {"photos": [dict(r) for r in rows], "total": total, "hasMore": offset + limit < total}
    finally:
        conn.close()


@router.get("/api/park/{park_id}/green-days")
async def get_green_days(park_id: str, month: str = None):
    park = get_park(park_id)
    if not park:
        return JSONResponse({"error": "Парк не найден"}, status_code=404)

    if not month:
        now = datetime.now(MOSCOW_TZ)
        month = now.strftime("%Y-%m")

    from services.soil_calculator import calculate_green_days

    year_s, month_s = month.split("-")
    year, mon = int(year_s), int(month_s)
    start_date = f"{month}-01"
    import calendar as _cal
    _, last_day = _cal.monthrange(year, mon)
    end_date = f"{month}-{last_day}"

    start_with_buffer = (
        datetime(year, mon, 1, tzinfo=MOSCOW_TZ) - timedelta(days=14)
    ).strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM weather_hourly
            WHERE park_id = ? AND timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (park_id, start_with_buffer, f"{end_date}T23:59:59")).fetchall()
        all_data = [dict(r) for r in rows]
    finally:
        conn.close()

    if not all_data:
        return {"park_id": park_id, "month": month, "days": []}

    days = calculate_green_days(park, all_data, month)
    return {"park_id": park_id, "month": month, "days": days}


@router.get("/park/{park_id}/calendar")
async def park_calendar_page(park_id: str):
    park = get_park(park_id)
    if not park:
        return HTMLResponse("<h1>Парк не найден</h1>", status_code=404)

    now = datetime.now(MOSCOW_TZ)
    current_month = now.strftime("%Y-%m")
    park_name = _html.escape(park["name"])
    park_id_esc = park_id.replace("\\", "\\\\").replace('"', '\\"')

    html = CALENDAR_HTML_TEMPLATE.replace("{{ park_name }}", park_name).replace("{{ park_id }}", park_id_esc).replace("{{ current_month }}", current_month)
    return HTMLResponse(html)