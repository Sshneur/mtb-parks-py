from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.encoders import jsonable_encoder
from database.connection import get_connection
from api.dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Add new columns if missing (safe migration)
try:
    c = get_connection()
    for col in ['frame_material', 'tire_brand', 'shock_travel_mm']:
        c.execute(f"ALTER TABLE bikes ADD COLUMN {col} TEXT")
    c.commit()
    c.close()
except Exception as e:
    logger.error(f"Миграция колонок bikes пропущена: {e}")

class BikeFullCreate(BaseModel):
    name: str
    bike_type: str = 'mtb'
    rider_weight_kg: Optional[float] = 75
    tire_type: str = 'mtb'
    tire_brand: Optional[str] = None
    frame_material: Optional[str] = None
    suspension_type: str = 'front_rear'
    wheel_size: str = '29'
    front_tire_width_mm: Optional[float] = None
    front_tire_pressure_psi: Optional[float] = None
    rear_tire_width_mm: Optional[float] = None
    rear_tire_pressure_psi: Optional[float] = None
    fork_brand: Optional[str] = None
    fork_model: Optional[str] = None
    fork_travel_mm: Optional[int] = None
    fork_pressure_psi: Optional[float] = None
    fork_rebound_clicks: Optional[int] = None
    fork_compression_clicks: Optional[int] = None
    fork_sag_mm: Optional[float] = None
    fork_damper: Optional[str] = None
    fork_hsc_clicks: Optional[int] = None
    fork_lsc_clicks: Optional[int] = None
    fork_hsr_clicks: Optional[int] = None
    fork_lsr_clicks: Optional[int] = None
    shock_brand: Optional[str] = None
    shock_model: Optional[str] = None
    shock_travel_mm: Optional[int] = None
    shock_pressure_psi: Optional[float] = None
    shock_rebound_clicks: Optional[int] = None
    shock_compression_clicks: Optional[int] = None
    shock_sag_mm: Optional[float] = None
    shock_damper: Optional[str] = None
    shock_hsc_clicks: Optional[int] = None
    shock_lsc_clicks: Optional[int] = None
    shock_hsr_clicks: Optional[int] = None
    shock_lsr_clicks: Optional[int] = None
    groupset: Optional[str] = None
    brakes: Optional[str] = None
    rotor_size_front_mm: Optional[int] = None
    rotor_size_rear_mm: Optional[int] = None
    handlebar_width_mm: Optional[int] = None
    stem_length_mm: Optional[int] = None
    dropper_travel_mm: Optional[int] = None

ALL_COLS = [
    "id","user_id","name","photo","rider_weight_kg","tire_type","tire_brand","frame_material","created_at",
    "bike_type","suspension_type","wheel_size",
    "front_tire_width_mm","front_tire_pressure_psi",
    "rear_tire_width_mm","rear_tire_pressure_psi",
    "fork_brand","fork_model","fork_travel_mm",
    "fork_pressure_psi","fork_rebound_clicks","fork_compression_clicks","fork_sag_mm",
    "fork_damper","fork_hsc_clicks","fork_lsc_clicks","fork_hsr_clicks","fork_lsr_clicks",
    "shock_brand","shock_model","shock_travel_mm",
    "shock_pressure_psi","shock_rebound_clicks","shock_compression_clicks","shock_sag_mm",
    "shock_damper","shock_hsc_clicks","shock_lsc_clicks","shock_hsr_clicks","shock_lsr_clicks",
    "groupset","brakes","rotor_size_front_mm","rotor_size_rear_mm",
    "handlebar_width_mm","stem_length_mm","dropper_travel_mm",
]

def bike_to_dict(row):
    d = dict(row)
    for k,v in d.items():
        if isinstance(v, float) and v != v:
            d[k] = None
    return d

def bike_list_full(user_id: int):
    conn = get_connection()
    try:
        cols = ", ".join(ALL_COLS)
        rows = conn.execute(
            f"SELECT {cols} FROM bikes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [bike_to_dict(r) for r in rows]
    finally:
        conn.close()

@router.get("/api/user/bikes/full")
async def get_bikes_full(user=Depends(get_current_user)):
    return bike_list_full(user["user_id"])

@router.get("/api/user/bikes/full/{bike_id}")
async def get_bike_full(bike_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        cols = ", ".join(ALL_COLS)
        row = conn.execute(
            f"SELECT {cols} FROM bikes WHERE id = ? AND user_id = ?",
            (bike_id, user["user_id"])
        ).fetchone()
        if not row:
            raise HTTPException(404, "Байк не найден")
        return bike_to_dict(row)
    finally:
        conn.close()

@router.post("/api/user/bikes/full")
async def create_bike_full(bike: BikeFullCreate, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        cols = [
            "user_id","name","bike_type","rider_weight_kg","tire_type","tire_brand","frame_material",
            "suspension_type","wheel_size",
            "front_tire_width_mm","front_tire_pressure_psi",
            "rear_tire_width_mm","rear_tire_pressure_psi",
            "fork_brand","fork_model","fork_travel_mm",
            "fork_pressure_psi","fork_rebound_clicks","fork_compression_clicks","fork_sag_mm",
            "fork_damper","fork_hsc_clicks","fork_lsc_clicks","fork_hsr_clicks","fork_lsr_clicks",
            "shock_brand","shock_model","shock_travel_mm",
            "shock_pressure_psi","shock_rebound_clicks","shock_compression_clicks","shock_sag_mm",
            "shock_damper","shock_hsc_clicks","shock_lsc_clicks","shock_hsr_clicks","shock_lsr_clicks",
            "groupset","brakes","rotor_size_front_mm","rotor_size_rear_mm",
            "handlebar_width_mm","stem_length_mm","dropper_travel_mm",
        ]
        ph = ",".join("?" for _ in cols)
        vals = [user["user_id"]] + [getattr(bike, c) for c in cols[1:]]
        cur = conn.execute(
            f"INSERT INTO bikes ({','.join(cols)}) VALUES ({ph})", vals
        )
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}
    finally:
        conn.close()

@router.put("/api/user/bikes/full/{bike_id}")
async def update_bike_full(bike_id: int, bike: BikeFullCreate, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM bikes WHERE id = ? AND user_id = ?",
            (bike_id, user["user_id"])
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Байк не найден")
        updates = {}
        for col in ALL_COLS:
            if col in ("id","user_id","created_at","photo"):
                continue
            updates[col] = getattr(bike, col, None)
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [bike_id, user["user_id"]]
            conn.execute(
                f"UPDATE bikes SET {set_clause} WHERE id = ? AND user_id = ?", vals
            )
            conn.commit()
        return {"ok": True}
    finally:
        conn.close()

GARAGE_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<title>🚲 Гараж</title>
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
.container { max-width: 900px; margin: 0 auto; padding: 16px; }
.back-link { display:inline-block; margin-bottom:16px; color:var(--accent); text-decoration:none; font-size:0.9rem; }
.back-link:hover { text-decoration:underline; }
h1 { font-size:1.5rem; margin-bottom:20px; display:flex; align-items:center; gap:8px; }
.card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:14px; padding:16px; margin-bottom:16px; }
.card h2 { font-size:1.1rem; margin-bottom:12px; color:var(--accent); }
.form-group { margin-bottom:12px; }
.form-group label { display:block; font-size:0.8rem; color:var(--text-muted); margin-bottom:4px; font-weight:500; }
.form-group input, .form-group select, .form-group textarea {
    width:100%; padding:10px 12px; border:1px solid var(--card-border); border-radius:8px;
    background:var(--bg-end); color:var(--text); font-size:0.9rem; font-family:inherit;
}
.form-group input:focus, .form-group select:focus { outline:none; border-color:var(--accent); }
.form-row { display:flex; gap:12px; }
.form-row .form-group { flex:1; }
.form-section { margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--card-border); }
.form-section:last-child { border-bottom:none; margin-bottom:0; }
.form-section h3 { font-size:1rem; margin-bottom:12px; color:var(--text); }
.btn { display:inline-block; padding:10px 20px; border:none; border-radius:10px; font-size:0.9rem; cursor:pointer; font-weight:600; transition:all 0.2s; }
.btn-primary { background:#4caf50; color:#fff; }
.btn-primary:hover { background:#43a047; }
.btn-secondary { background:rgba(74,144,226,0.15); color:var(--accent); }
.btn-secondary:hover { background:rgba(74,144,226,0.25); }
.btn-danger { background:#e74c3c; color:#fff; }
.btn-danger:hover { background:#c0392b; }
.btn-sm { padding:6px 12px; font-size:0.8rem; }
.bike-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:16px; }
.bike-card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:14px; padding:16px; cursor:pointer; transition:all 0.2s; }
.bike-card:hover { border-color:var(--card-border-hover); }
.bike-card h3 { font-size:1rem; margin-bottom:6px; }
.bike-card .meta { font-size:0.8rem; color:var(--text-muted); }
.bike-card .tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:8px; }
.bike-card .tags span { font-size:0.65rem; padding:2px 8px; border-radius:20px; background:rgba(74,144,226,0.12); color:var(--accent); }
.bike-card-actions { margin-top:12px; display:flex; gap:8px; }
#bikeForm { display:none; }
#authRequired { text-align:center; padding:60px 20px; }
#authRequired h2 { margin-bottom:12px; }
#authRequired a { color:var(--accent); }
.empty-state { text-align:center; padding:40px 20px; color:var(--text-muted); font-size:0.9rem; }
.empty-state .big-icon { font-size:3rem; margin-bottom:12px; }
.dashboard-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.dash-card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:14px; padding:14px 16px; display:flex; flex-direction:column; }
.dash-card.full { grid-column:1/-1; }
.dash-card h2 { font-size:0.85rem; margin-bottom:10px; color:var(--accent); display:flex; align-items:center; gap:6px; }
.dash-row { display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid rgba(128,128,128,0.06); }
.dash-row:last-child { border-bottom:none; }
.dash-row .lbl { color:var(--text-muted); font-size:0.78rem; }
.dash-row .val { font-weight:600; font-size:0.85rem; text-align:right; }
.badge { display:inline-block; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }
.badge-mtb { background:rgba(76,175,80,0.15); color:#4caf50; }
.badge-enduro { background:rgba(255,152,0,0.15); color:#ff9800; }
.badge-dh { background:rgba(233,30,99,0.15); color:#e91e63; }
.badge-trail { background:rgba(33,150,243,0.15); color:#2196f3; }
.badge-xc { background:rgba(156,39,176,0.15); color:#9c27b0; }
.badge-gravel { background:rgba(139,195,74,0.15); color:#8bc34a; }
.badge-road { background:rgba(158,158,158,0.15); color:#9e9e9e; }
.avatar-img { width:50px; height:50px; border-radius:50%; object-fit:cover; border:2px solid var(--card-border); }
.avatar-placeholder { width:50px; height:50px; border-radius:50%; background:rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:center; font-size:1.4rem; color:var(--text-muted); }
</style>
<script defer src="https://gripcheck.ru/x.js" data-website-id="b88aec0e-21c1-445a-9ce2-566959574f4f" data-domains="gripcheck.ru,xn--80afdaebh7a3c.xn--p1ai" data-do-not-track="true"></script>
</head>
<body>
<div class="container">
    <a href="/" class="back-link">← На главную</a>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h1 style="font-size:1.3rem; margin:0;">🚲 Мой гараж</h1>
        <button id="authToggleBtn" style="background:none; border:none; font-size:1.3rem; cursor:pointer; padding:4px 8px; line-height:1; color:var(--text);">🌙</button>
    </div>

    <div id="authRequired" style="display:none;">
        <div class="big-icon">🔒</div>
        <h2>Войдите в профиль</h2>
        <p style="color:var(--text-muted);">Чтобы управлять гаражом, <a href="/login">войдите</a> или <a href="/register">зарегистрируйтесь</a></p>
    </div>

    <div id="garageContent" style="display:none;">
        <div id="bikeListContainer"></div>
        <button class="btn btn-primary" id="addBikeBtn" style="width:100%; margin-top:8px;">+ Добавить байк</button>

        <div id="bikeForm" class="card" style="margin-top:16px;">
            <h2 id="formTitle">Новый байк</h2>

            <div class="form-section">
                <h3>📋 Основное</h3>
                <div class="form-group">
                    <label>Название байка</label>
                    <input type="text" id="f_name" placeholder="Например: Kona Process 134">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Тип велосипеда</label>
                        <select id="f_bike_type">
                            <option value="mtb">MTB</option>
                            <option value="enduro">Эндуро</option>
                            <option value="trail">Трейл</option>
                            <option value="downhill">Даунхилл</option>
                            <option value="xc">XC</option>
                            <option value="gravel">Гравел</option>
                            <option value="road">Шоссе</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Тип резины</label>
                        <select id="f_tire_type">
                            <option value="mtb">MTB (2.2-2.5")</option>
                            <option value="mtb_plus">MTB Plus (2.5-3.0")</option>
                            <option value="gravel">Гравел</option>
                            <option value="road">Шоссе</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Марка резины</label>
                        <input type="text" id="f_tire_brand" placeholder="Напр. Vittoria, Maxxis">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Мой вес (кг)</label>
                        <input type="number" id="f_rider_weight" value="75" min="30" max="200">
                    </div>
                    <div class="form-group">
                        <label>Размер колёс</label>
                        <select id="f_wheel_size">
                            <option value="29">29"</option>
                            <option value="27.5">27.5"</option>
                            <option value="26">26"</option>
                            <option value="mullet">МАЛЛЕТ (29"F + 27.5"R)</option>
                            <option value="650b">650B</option>
                            <option value="700c">700C</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Материал рамы</label>
                        <select id="f_frame_material">
                            <option value="">—</option>
                            <option value="carbon">Карбон</option>
                            <option value="aluminum">Алюминий</option>
                            <option value="steel">Сталь</option>
                            <option value="titanium">Титан</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="form-section">
                <h3>🛞 Колёса и резина</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Перед — ширина (любые единицы)</label>
                        <input type="number" step="0.1" id="f_front_tire_width" placeholder="Напр. 2.5">
                    </div>
                    <div class="form-group">
                        <label>Перед — давление (PSI)</label>
                        <input type="number" id="f_front_tire_pressure" placeholder="Напр. 28">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Зад — ширина (любые единицы)</label>
                        <input type="number" step="0.1" id="f_rear_tire_width" placeholder="Напр. 2.4">
                    </div>
                    <div class="form-group">
                        <label>Зад — давление (PSI)</label>
                        <input type="number" id="f_rear_tire_pressure" placeholder="Напр. 30">
                    </div>
                </div>
            </div>

            <div class="form-section">
                <h3>🔧 Подвеска</h3>
                <div class="form-group">
                    <label>Тип подвески</label>
                    <select id="f_suspension_type">
                        <option value="front_rear">Передняя + задняя</option>
                        <option value="front_only">Только передняя</option>
                        <option value="rigid">Жёсткая (без подвески)</option>
                    </select>
                </div>
            </div>

            <div id="forkSection" class="form-section">
                <h3>📌 Вилка</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Бренд</label>
                        <select id="f_fork_brand">
                            <option value="">— выберите —</option>
                            <option value="rockshox">RockShox</option>
                            <option value="fox">FOX</option>
                            <option value="suntour">Suntour</option>
                            <option value="other">Другое</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Модель</label>
                        <input type="text" id="f_fork_model" placeholder="Напр. Lyrik Select+">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Ход (мм)</label>
                        <input type="number" id="f_fork_travel" placeholder="Напр. 160">
                    </div>
                    <div class="form-group">
                        <label>Давление (PSI)</label>
                        <input type="number" id="f_fork_pressure" placeholder="Напр. 85">
                    </div>
                </div>
                <div class="form-group">
                    <label>Картридж демпфера</label>
                    <select id="f_fork_damper" onchange="toggleForkDamper()">
                        <option value="">— выберите картридж —</option>
                        <optgroup label="FOX">
                            <option value="fox_grip">GRIP (3-поз. рычаг)</option>
                            <option value="fox_grip_x">GRIP X (LSC + LSR)</option>
                            <option value="fox_grip2">GRIP2 (HSC/LSC + HSR/LSR)</option>
                            <option value="fox_grip_x2">GRIP X2 (HSC/LSC + HSR/LSR)</option>
                            <option value="fox_fit4">FIT4 (3-поз. + LSC)</option>
                        </optgroup>
                        <optgroup label="RockShox">
                            <option value="rs_charger_2">Charger 2 (LSC + LSR)</option>
                            <option value="rs_charger_21">Charger 2.1 (LSC + LSR)</option>
                            <option value="rs_charger_3">Charger 3 (LSC + LSR)</option>
                            <option value="rs_charger_rd2">Charger Race Day 2 (2-поз. + LSR)</option>
                        </optgroup>
                        <optgroup label="Suntour">
                            <option value="st_qr">QR (LSR)</option>
                            <option value="st_qlr">QLR (LSC + LSR)</option>
                        </optgroup>
                    </select>
                </div>

                <div id="forkDamperSimple" style="display:none;">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Отскок (клики)</label>
                            <input type="number" id="f_fork_rebound" placeholder="Напр. 8">
                        </div>
                        <div class="form-group">
                            <label>Компрессия (клики)</label>
                            <input type="number" id="f_fork_compression" placeholder="Напр. 6">
                        </div>
                    </div>
                </div>

                <div id="forkDamperFull" style="display:none;">
                    <div class="form-row">
                        <div class="form-group">
                            <label>HSC — Высокоск. компрессия (клики)</label>
                            <input type="number" id="f_fork_hsc" placeholder="Напр. 6">
                        </div>
                        <div class="form-group">
                            <label>LSC — Низкоск. компрессия (клики)</label>
                            <input type="number" id="f_fork_lsc" placeholder="Напр. 8">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>HSR — Высокоск. отскок (клики)</label>
                            <input type="number" id="f_fork_hsr" placeholder="Напр. 5">
                        </div>
                        <div class="form-group">
                            <label>LSR — Низкоск. отскок (клики)</label>
                            <input type="number" id="f_fork_lsr" placeholder="Напр. 10">
                        </div>
                    </div>
                </div>

                <div class="form-group">
                    <label>Сэг (%)</label>
                    <input type="number" id="f_fork_sag" placeholder="Напр. 20">
                </div>
            </div>

            <div id="shockSection" class="form-section">
                <h3>📌 Амортизатор</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Бренд</label>
                        <select id="f_shock_brand">
                            <option value="">— выберите —</option>
                            <option value="rockshox">RockShox</option>
                            <option value="fox">FOX</option>
                            <option value="suntour">Suntour</option>
                            <option value="other">Другое</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Модель</label>
                        <input type="text" id="f_shock_model" placeholder="Напр. Super Deluxe">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Ход (мм)</label>
                        <input type="number" id="f_shock_travel" placeholder="Напр. 55">
                    </div>
                    <div class="form-group">
                        <label>Давление (PSI)</label>
                        <input type="number" id="f_shock_pressure" placeholder="Напр. 200">
                    </div>
                </div>
                <div class="form-group">
                    <label>Картридж демпфера</label>
                    <select id="f_shock_damper" onchange="toggleShockDamper()">
                        <option value="">— выберите картридж —</option>
                        <optgroup label="FOX">
                            <option value="fox_dps">FLOAT DPS (3-поз. + LSR)</option>
                            <option value="fox_x2">FLOAT X2 / DHX2 (HSC/LSC + HSR/LSR)</option>
                        </optgroup>
                        <optgroup label="RockShox">
                            <option value="rs_sd">Super Deluxe (3-поз. + LSR)</option>
                            <option value="rs_sd_rc2t">Super Deluxe RC2T (HSC/LSC + LSR)</option>
                            <option value="rs_vivid">Vivid (HSR + LSR)</option>
                            <option value="rs_vivid_ult">Vivid Ultimate (HSC/LSC + HSR/LSR)</option>
                        </optgroup>
                    </select>
                </div>

                <div id="shockDamperSimple" style="display:none;">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Отскок (клики)</label>
                            <input type="number" id="f_shock_rebound" placeholder="Напр. 10">
                        </div>
                        <div class="form-group">
                            <label>Компрессия (клики)</label>
                            <input type="number" id="f_shock_compression" placeholder="Напр. 8">
                        </div>
                    </div>
                </div>

                <div id="shockDamperFull" style="display:none;">
                    <div class="form-row">
                        <div class="form-group">
                            <label>HSC — Высокоск. компрессия (клики)</label>
                            <input type="number" id="f_shock_hsc" placeholder="Напр. 4">
                        </div>
                        <div class="form-group">
                            <label>LSC — Низкоск. компрессия (клики)</label>
                            <input type="number" id="f_shock_lsc" placeholder="Напр. 8">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>HSR — Высокоск. отскок (клики)</label>
                            <input type="number" id="f_shock_hsr" placeholder="Напр. 6">
                        </div>
                        <div class="form-group">
                            <label>LSR — Низкоск. отскок (клики)</label>
                            <input type="number" id="f_shock_lsr" placeholder="Напр. 12">
                        </div>
                    </div>
                </div>

                <div class="form-group">
                    <label>Сэг (%)</label>
                    <input type="number" id="f_shock_sag" placeholder="Напр. 25">
                </div>
            </div>

            <div class="form-section">
                <h3>⚙️ Компоненты</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Групсет</label>
                        <input type="text" id="f_groupset" placeholder="Напр. SRAM GX Eagle">
                    </div>
                    <div class="form-group">
                        <label>Тормоза</label>
                        <input type="text" id="f_brakes" placeholder="Напр. Shimano SLX">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Ротор передний (мм)</label>
                        <input type="number" id="f_rotor_front" placeholder="Напр. 203">
                    </div>
                    <div class="form-group">
                        <label>Ротор задний (мм)</label>
                        <input type="number" id="f_rotor_rear" placeholder="Напр. 180">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Ширина руля (мм)</label>
                        <input type="number" id="f_handlebar_width" placeholder="Напр. 780">
                    </div>
                    <div class="form-group">
                        <label>Длина выноса (мм)</label>
                        <input type="number" id="f_stem_length" placeholder="Напр. 50">
                    </div>
                </div>
                <div class="form-group">
                    <label>Ход дроппера (мм)</label>
                    <input type="number" id="f_dropper_travel" placeholder="Напр. 170">
                </div>
            </div>

            <div style="display:flex; gap:8px; margin-top:16px; padding-top:16px; border-top:1px solid var(--card-border);">
                <button class="btn btn-primary" id="saveBikeBtn">💾 Сохранить</button>
                <button class="btn btn-secondary" id="cancelBikeBtn">Отмена</button>
            </div>
        </div>

        <div id="bikeDashboard" style="display:none; margin-top:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <h2 id="dashboardTitle" style="font-size:1.3rem;"></h2>
                <div>
                    <button class="btn btn-secondary btn-sm" id="editBikeBtn">✏️</button>
                    <button class="btn btn-danger btn-sm" id="deleteBikeBtn" style="margin-left:4px;">🗑️</button>
                </div>
            </div>
            <div id="dashboardContent" class="dashboard-grid"></div>
            <div style="margin-top:12px;">
                <button class="btn btn-secondary btn-sm" id="copyBikeBtn">📋 Копировать</button>
            </div>
        </div>

        <div id="profileSection" class="card" style="margin-top:24px; display:none;">
            <h2 style="font-size:1rem; margin-bottom:14px;">🔧 Профиль</h2>
            <div style="display:flex; align-items:center; gap:14px; margin-bottom:16px;">
                <div id="profileAvatar"></div>
                <div style="flex:1;">
                    <div id="profileName" style="font-weight:600;"></div>
                    <div id="profileEmail" style="font-size:0.8rem; color:var(--text-muted);"></div>
                </div>
            </div>
            <div id="favSection" style="margin-bottom:16px;">
                <div style="font-size:0.85rem; color:var(--accent); margin-bottom:8px;">⭐ Избранные парки</div>
                <div id="favList"></div>
            </div>
            <div style="padding-top:14px; border-top:1px solid var(--card-border);">
                <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;">Рассчитать давление в шинах:</div>
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                    <a href="https://axs.sram.com/tirepressureguide" target="_blank" style="flex:1; text-align:center; padding:10px; background:#fa0; color:#000; border-radius:10px; text-decoration:none; font-weight:700; min-width:100px; font-size:0.85rem;">SRAM</a>
                    <a href="https://int.vittoria.com/pages/tire-pressure" target="_blank" style="flex:1; text-align:center; padding:10px; background:#e74c3c; color:#fff; border-radius:10px; text-decoration:none; font-weight:600; min-width:100px; font-size:0.85rem;">Vittoria</a>
                    <a href="https://www.schwalbe.com/pressureprof/" target="_blank" style="flex:1; text-align:center; padding:10px; background:#3498db; color:#fff; border-radius:10px; text-decoration:none; font-weight:600; min-width:100px; font-size:0.85rem;">Schwalbe</a>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
(function(){
    var tBtn = document.getElementById('authToggleBtn');
    if (tBtn) {
        tBtn.textContent = document.documentElement.classList.contains('theme-light') ? '☀️' : '🌙';
        tBtn.addEventListener('click', function(){
            document.documentElement.classList.toggle('theme-light');
            var l = document.documentElement.classList.contains('theme-light');
            localStorage.setItem('theme', l ? 'light' : 'dark');
            tBtn.textContent = l ? '☀️' : '🌙';
        });
    }
})();

    var TOKEN = localStorage.getItem('token');

        function escapeHtml(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
    if (!TOKEN) {
        document.getElementById('authRequired').style.display = 'block';
    } else {
        document.getElementById('garageContent').style.display = 'block';
        var editingBikeId = null;
        var bikes = [];

        function loadProfileSection() {
            fetch('/api/user/profile', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
                .then(function(r){ if (!r.ok) return; return r.json(); })
                .then(function(p){
                    if (!p) return;
                    document.getElementById('profileSection').style.display = 'block';
                    document.getElementById('profileName').textContent = p.username || 'Пользователь';
                    document.getElementById('profileEmail').textContent = p.email;
                    var aw = document.getElementById('profileAvatar');
                    if (p.avatar) { aw.innerHTML = '<img src="' + escapeHtml(p.avatar) + '" class="avatar-img">'; }
                    else { aw.innerHTML = '<div class="avatar-placeholder">' + escapeHtml(p.username ? p.username[0].toUpperCase() : '?') + '</div>'; }
                    var favList = document.getElementById('favList');
                    if (p.favorites && p.favorites.length) {
                        favList.innerHTML = p.favorites.map(function(f){ return '<span style="display:inline-block;padding:3px 10px;margin:2px;background:rgba(74,144,226,0.12);border-radius:6px;font-size:0.8rem;"><a href="/park/' + escapeHtml(f.id) + '" style="color:var(--text);text-decoration:none;">' + escapeHtml(f.name || f.id) + '</a></span>'; }).join('');
                    } else {
                        favList.innerHTML = '<div style="font-size:0.8rem;color:var(--text-muted);">Нет избранных парков</div>';
                    }
                });
        }

    function selectBike(id) {
        loadBikeForm();
        editingBikeId = id;
        fetch('/api/user/bikes/full/' + id + '?_=' + Date.now(), { headers: { 'Authorization': 'Bearer ' + TOKEN } })
            .then(function(r){ return r.json(); })
            .then(function(bike){ showDashboard(bike); });
    }

    function copyBikeData(b) {
        var lines = [];
        function a(lbl, val) { if (val !== null && val !== undefined && val !== '' && val !== '—') lines.push(lbl + ': ' + val); }
        lines.push('🚲 ' + (b.name || 'Байк'));
        lines.push('');
        a('Тип', b.bike_type);
        a('Райдер', b.rider_weight_kg ? b.rider_weight_kg + ' кг' : null);
        if (b.wheel_size) {
            var ws = b.wheel_size;
            if (ws === 'mullet') ws = '29"F / 27.5"R';
            else ws = ws + '"';
            a('Колёса', ws);
        }
        var tire = b.tire_type || '';
        if (b.tire_brand) tire = b.tire_brand + ' ' + tire;
        a('Резина', tire || null);
        a('Рама', b.frame_material ? b.frame_material.charAt(0).toUpperCase() + b.frame_material.slice(1) : null);
        lines.push('');
        lines.push('🛞 Колёса');
        a('Перед', b.front_tire_width_mm ? b.front_tire_width_mm + '"' : null);
        a('Перед давление', b.front_tire_pressure_psi ? b.front_tire_pressure_psi + ' PSI' : null);
        a('Зад', b.rear_tire_width_mm ? b.rear_tire_width_mm + '"' : null);
        a('Зад давление', b.rear_tire_pressure_psi ? b.rear_tire_pressure_psi + ' PSI' : null);
        if (b.rotor_size_front_mm || b.rotor_size_rear_mm) a('Роторы', (b.rotor_size_front_mm || '?') + 'F / ' + (b.rotor_size_rear_mm || '?') + 'R мм');
        if (b.fork_brand) {
            lines.push('');
            lines.push('📌 Вилка');
            a('Модель', b.fork_brand + (b.fork_model ? ' ' + b.fork_model : '') + (b.fork_travel_mm ? ' ' + b.fork_travel_mm + 'mm' : ''));
            a('Давление', b.fork_pressure_psi ? b.fork_pressure_psi + ' PSI' : null);
            a('Сэг', b.fork_sag_mm ? b.fork_sag_mm + '%' : null);
            if (b.fork_damper) {
                var dl = {'fox_grip':'GRIP','fox_grip_x':'GRIP X','fox_grip2':'GRIP2','fox_grip_x2':'GRIP X2','fox_fit4':'FIT4','rs_charger_2':'Charger 2','rs_charger_21':'Charger 2.1','rs_charger_3':'Charger 3','rs_charger_rd2':'Race Day 2','st_qr':'QR','st_qlr':'QLR'};
                a('Демпфер', dl[b.fork_damper] || b.fork_damper);
                if (b.fork_hsc_clicks !== null && b.fork_hsc_clicks !== undefined) a('HSC', b.fork_hsc_clicks);
                if (b.fork_lsc_clicks !== null && b.fork_lsc_clicks !== undefined) a('LSC', b.fork_lsc_clicks);
                if (b.fork_hsr_clicks !== null && b.fork_hsr_clicks !== undefined) a('HSR', b.fork_hsr_clicks);
                if (b.fork_lsr_clicks !== null && b.fork_lsr_clicks !== undefined) a('LSR', b.fork_lsr_clicks);
            }
        }
        if (b.suspension_type === 'front_rear' && b.shock_brand) {
            lines.push('');
            lines.push('🔧 Амортизатор');
            a('Модель', b.shock_brand + (b.shock_model ? ' ' + b.shock_model : '') + (b.shock_travel_mm ? ' ' + b.shock_travel_mm + 'mm' : ''));
            a('Давление', b.shock_pressure_psi ? b.shock_pressure_psi + ' PSI' : null);
            a('Сэг', b.shock_sag_mm ? b.shock_sag_mm + '%' : null);
            if (b.shock_damper) {
                var sdl = {'fox_dps':'FLOAT DPS','fox_x2':'FLOAT X2/DHX2','rs_sd':'Super Deluxe','rs_sd_rc2t':'SD RC2T','rs_vivid':'Vivid','rs_vivid_ult':'Vivid Ultimate'};
                a('Демпфер', sdl[b.shock_damper] || b.shock_damper);
                if (b.shock_hsc_clicks !== null && b.shock_hsc_clicks !== undefined) a('HSC', b.shock_hsc_clicks);
                if (b.shock_lsc_clicks !== null && b.shock_lsc_clicks !== undefined) a('LSC', b.shock_lsc_clicks);
                if (b.shock_hsr_clicks !== null && b.shock_hsr_clicks !== undefined) a('HSR', b.shock_hsr_clicks);
                if (b.shock_lsr_clicks !== null && b.shock_lsr_clicks !== undefined) a('LSR', b.shock_lsr_clicks);
            }
        }
        if (b.groupset || b.brakes || b.handlebar_width_mm || b.stem_length_mm || b.dropper_travel_mm) {
            lines.push('');
            lines.push('⚙️ Компоненты');
            a('Групсет', b.groupset);
            a('Тормоза', b.brakes);
            a('Руль', b.handlebar_width_mm ? b.handlebar_width_mm + ' мм' : null);
            a('Вынос', b.stem_length_mm ? b.stem_length_mm + ' мм' : null);
            a('Дроппер', b.dropper_travel_mm ? b.dropper_travel_mm + ' мм' : null);
        }
        var text = lines.join('\n');
        navigator.clipboard.writeText(text).then(function(){
            if (window.umami) umami.track('bike_copy');
            var btn = document.getElementById('copyBikeBtn');
            btn.textContent = '✅ Скопировано';
            setTimeout(function(){ btn.textContent = '📋 Копировать'; }, 2000);
        });
    }

    function showDashboard(bike) {
        document.getElementById('bikeListContainer').style.display = 'none';
        document.getElementById('addBikeBtn').style.display = 'none';
        document.getElementById('bikeForm').style.display = 'none';
        document.getElementById('bikeDashboard').style.display = 'block';
        document.getElementById('dashboardTitle').textContent = '🚲 ' + bike.name;
        document.getElementById('editBikeBtn').onclick = function(){ editBike(bike); };
        document.getElementById('deleteBikeBtn').onclick = function(){ deleteBike(bike.id); };
        document.getElementById('copyBikeBtn').onclick = function(){ copyBikeData(bike); };

        function fmtPSI(v) { return v ? v + ' PSI' : '—'; }
        var ws = bike.wheel_size || '29';
        if (bike.wheel_size === 'mullet') ws = '29"F / 27.5"R';
        else ws = ws + '"';

        var html = '';

        // Байк
        var tireStr = bike.tire_type ? bike.tire_type.replace('mtb','MTB').replace('_plus','+').replace('gravel','Гравел').replace('road','Шоссе') : '';
        if (bike.tire_brand) tireStr = bike.tire_brand + ' ' + tireStr;
        html += '<div class="dash-card"><h2>🚲 ' + escapeHtml(bike.name) + '</h2>';
        html += '<div class="dash-row"><span class="lbl">Тип</span><span class="val"><span class="badge badge-' + (bike.bike_type || 'mtb') + '">' + (bike.bike_type || 'MTB') + '</span></span></div>';
        html += '<div class="dash-row"><span class="lbl">Райдер</span><span class="val">' + bike.rider_weight_kg + ' кг</span></div>';
        html += '<div class="dash-row"><span class="lbl">Колёса</span><span class="val">' + ws + '</span></div>';
        if (tireStr) html += '<div class="dash-row"><span class="lbl">Резина</span><span class="val">' + escapeHtml(tireStr) + '</span></div>';
        if (bike.frame_material) html += '<div class="dash-row"><span class="lbl">Рама</span><span class="val">' + escapeHtml(bike.frame_material.charAt(0).toUpperCase() + bike.frame_material.slice(1)) + '</span></div>';
        html += '</div>';

        // Колёса
        html += '<div class="dash-card"><h2>🛞 Колёса</h2>';
        html += '<div class="dash-row"><span class="lbl">Перед</span><span class="val">' + (bike.front_tire_width_mm || '—') + '" ' + fmtPSI(bike.front_tire_pressure_psi) + '</span></div>';
        html += '<div class="dash-row"><span class="lbl">Зад</span><span class="val">' + (bike.rear_tire_width_mm || '—') + '" ' + fmtPSI(bike.rear_tire_pressure_psi) + '</span></div>';
        if (bike.rotor_size_front_mm || bike.rotor_size_rear_mm) html += '<div class="dash-row"><span class="lbl">Роторы</span><span class="val">' + (bike.rotor_size_front_mm || '?') + 'F / ' + (bike.rotor_size_rear_mm || '?') + 'R мм</span></div>';
        html += '</div>';

        // Амортизатор
        if (bike.suspension_type === 'front_rear' && bike.shock_brand) {
            html += '<div class="dash-card"><h2>🔧 Амортизатор</h2>';
            html += '<div class="dash-row"><span class="lbl">Модель</span><span class="val">' + escapeHtml(bike.shock_brand + (bike.shock_model ? ' ' + bike.shock_model : '')) + (bike.shock_travel_mm ? ' · ' + bike.shock_travel_mm + ' мм' : '') + '</span></div>';
            html += '<div class="dash-row"><span class="lbl">Давление</span><span class="val">' + fmtPSI(bike.shock_pressure_psi) + '</span></div>';
            html += '<div class="dash-row"><span class="lbl">Сэг</span><span class="val">' + (bike.shock_sag_mm || '—') + '%</span></div>';
            if (bike.shock_damper) {
                var sd = bike.shock_damper;
                var sdl = {'fox_dps':'FLOAT DPS','fox_x2':'FLOAT X2/DHX2','rs_sd':'Super Deluxe','rs_sd_rc2t':'SD RC2T','rs_vivid':'Vivid','rs_vivid_ult':'Vivid Ultimate'};
                html += '<div class="dash-row"><span class="lbl">Демпфер</span><span class="val">' + (sdl[sd] || sd) + '</span></div>';
                var isFull = sd === 'fox_x2' || sd === 'rs_sd_rc2t' || sd === 'rs_vivid_ult';
                var isSimple = sd === 'fox_dps' || sd === 'rs_sd' || sd === 'rs_vivid';
                if (isFull) {
                    if (bike.shock_hsc_clicks !== null && bike.shock_hsc_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">HSC</span><span class="val">' + bike.shock_hsc_clicks + '</span></div>';
                    if (bike.shock_lsc_clicks !== null && bike.shock_lsc_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">LSC</span><span class="val">' + bike.shock_lsc_clicks + '</span></div>';
                    if (bike.shock_hsr_clicks !== null && bike.shock_hsr_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">HSR</span><span class="val">' + bike.shock_hsr_clicks + '</span></div>';
                    if (bike.shock_lsr_clicks !== null && bike.shock_lsr_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">LSR</span><span class="val">' + bike.shock_lsr_clicks + '</span></div>';
                } else if (isSimple) {
                    if (bike.shock_rebound_clicks !== null && bike.shock_rebound_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Отскок</span><span class="val">' + bike.shock_rebound_clicks + '</span></div>';
                    if (bike.shock_compression_clicks !== null && bike.shock_compression_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Компрессия</span><span class="val">' + bike.shock_compression_clicks + '</span></div>';
                }
            }
            html += '</div>';
        }

        // Компоненты
        if (bike.groupset || bike.brakes || bike.handlebar_width_mm || bike.stem_length_mm || bike.dropper_travel_mm) {
            html += '<div class="dash-card"><h2>⚙️ Компоненты</h2>';
            if (bike.groupset) html += '<div class="dash-row"><span class="lbl">Групсет</span><span class="val">' + escapeHtml(bike.groupset) + '</span></div>';
            if (bike.brakes) html += '<div class="dash-row"><span class="lbl">Тормоза</span><span class="val">' + escapeHtml(bike.brakes) + '</span></div>';
            if (bike.handlebar_width_mm) html += '<div class="dash-row"><span class="lbl">Руль</span><span class="val">' + bike.handlebar_width_mm + ' мм</span></div>';
            if (bike.stem_length_mm) html += '<div class="dash-row"><span class="lbl">Вынос</span><span class="val">' + bike.stem_length_mm + ' мм</span></div>';
            if (bike.dropper_travel_mm) html += '<div class="dash-row"><span class="lbl">Дроппер</span><span class="val">' + bike.dropper_travel_mm + ' мм</span></div>';
            html += '</div>';
        }

        // Вилка — full width снизу (все клики на своих строках)
        if (bike.fork_brand) {
            var hasOther = (bike.suspension_type === 'front_rear' && bike.shock_brand) || (bike.groupset || bike.brakes || bike.handlebar_width_mm || bike.stem_length_mm || bike.dropper_travel_mm);
            html += '<div class="dash-card' + (hasOther ? ' full' : '') + '"><h2>📌 Вилка</h2>';
            html += '<div class="dash-row"><span class="lbl">Модель</span><span class="val">' + escapeHtml(bike.fork_brand + (bike.fork_model ? ' ' + bike.fork_model : '')) + (bike.fork_travel_mm ? ' · ' + bike.fork_travel_mm + ' мм' : '') + '</span></div>';
            html += '<div class="dash-row"><span class="lbl">Давление</span><span class="val">' + fmtPSI(bike.fork_pressure_psi) + '</span></div>';
            html += '<div class="dash-row"><span class="lbl">Сэг</span><span class="val">' + (bike.fork_sag_mm || '—') + '%</span></div>';
            if (bike.fork_damper) {
                var fd = bike.fork_damper;
                var dl = {'fox_grip':'GRIP','fox_grip_x':'GRIP X','fox_grip2':'GRIP2','fox_grip_x2':'GRIP X2','fox_fit4':'FIT4','rs_charger_2':'Charger 2','rs_charger_21':'Charger 2.1','rs_charger_3':'Charger 3','rs_charger_rd2':'Race Day 2','st_qr':'QR','st_qlr':'QLR'};
                html += '<div class="dash-row"><span class="lbl">Демпфер</span><span class="val">' + (dl[fd] || fd) + '</span></div>';
                var fIsFull = fd === 'fox_grip2' || fd === 'fox_grip_x2' || fd === 'rs_vivid_ult';
                var fIsSimple = fd === 'fox_grip_x' || fd === 'fox_fit4' || fd === 'rs_charger_2' || fd === 'rs_charger_21' || fd === 'rs_charger_3' || fd === 'st_qlr';
                if (fIsFull) {
                    if (bike.fork_hsc_clicks !== null && bike.fork_hsc_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">HSC</span><span class="val">' + bike.fork_hsc_clicks + '</span></div>';
                    if (bike.fork_lsc_clicks !== null && bike.fork_lsc_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">LSC</span><span class="val">' + bike.fork_lsc_clicks + '</span></div>';
                    if (bike.fork_hsr_clicks !== null && bike.fork_hsr_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">HSR</span><span class="val">' + bike.fork_hsr_clicks + '</span></div>';
                    if (bike.fork_lsr_clicks !== null && bike.fork_lsr_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">LSR</span><span class="val">' + bike.fork_lsr_clicks + '</span></div>';
                } else if (fIsSimple) {
                    if (bike.fork_rebound_clicks !== null && bike.fork_rebound_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Отскок</span><span class="val">' + bike.fork_rebound_clicks + '</span></div>';
                    if (bike.fork_compression_clicks !== null && bike.fork_compression_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Компрессия</span><span class="val">' + bike.fork_compression_clicks + '</span></div>';
                }
            } else {
                if (bike.fork_rebound_clicks !== null && bike.fork_rebound_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Отскок</span><span class="val">' + bike.fork_rebound_clicks + '</span></div>';
                if (bike.fork_compression_clicks !== null && bike.fork_compression_clicks !== undefined) html += '<div class="dash-row"><span class="lbl">Компрессия</span><span class="val">' + bike.fork_compression_clicks + '</span></div>';
            }
            html += '</div>';
        }

        document.getElementById('dashboardContent').innerHTML = html;
    }

    function editBike(bike) {
        document.getElementById('bikeDashboard').style.display = 'none';
        document.getElementById('bikeListContainer').style.display = 'block';
        document.getElementById('addBikeBtn').style.display = 'block';
        loadBikeForm(bike);
    }

    function loadBikeForm(bike) {
        _formLoading = true;
        var form = document.getElementById('bikeForm');
        form.style.display = 'block';
        document.getElementById('formTitle').textContent = bike ? '✏️ Редактировать байк' : 'Новый байк';
        document.getElementById('f_name').value = bike ? (bike.name || '') : '';
        document.getElementById('f_bike_type').value = bike ? (bike.bike_type || 'mtb') : 'mtb';
        document.getElementById('f_tire_type').value = bike ? (bike.tire_type || 'mtb') : 'mtb';
        document.getElementById('f_tire_brand').value = bike ? (bike.tire_brand || '') : '';
        document.getElementById('f_frame_material').value = bike ? (bike.frame_material || '') : '';
        document.getElementById('f_rider_weight').value = bike ? (bike.rider_weight_kg || 75) : 75;
        document.getElementById('f_wheel_size').value = bike ? (bike.wheel_size || '29') : '29';
        document.getElementById('f_front_tire_width').value = bike ? (bike.front_tire_width_mm || '') : '';
        document.getElementById('f_front_tire_pressure').value = bike ? (bike.front_tire_pressure_psi || '') : '';
        document.getElementById('f_rear_tire_width').value = bike ? (bike.rear_tire_width_mm || '') : '';
        document.getElementById('f_rear_tire_pressure').value = bike ? (bike.rear_tire_pressure_psi || '') : '';
        document.getElementById('f_suspension_type').value = bike ? (bike.suspension_type || 'front_rear') : 'front_rear';
        document.getElementById('f_fork_brand').value = bike ? (bike.fork_brand || '') : '';
        document.getElementById('f_fork_model').value = bike ? (bike.fork_model || '') : '';
        document.getElementById('f_fork_travel').value = bike ? (bike.fork_travel_mm || '') : '';
        document.getElementById('f_fork_pressure').value = bike ? (bike.fork_pressure_psi || '') : '';
        document.getElementById('f_fork_rebound').value = bike ? (bike.fork_rebound_clicks ?? '') : '';
        document.getElementById('f_fork_compression').value = bike ? (bike.fork_compression_clicks ?? '') : '';
        document.getElementById('f_fork_sag').value = bike ? (bike.fork_sag_mm || '') : '';
        document.getElementById('f_fork_damper').value = bike ? (bike.fork_damper || '') : '';
        document.getElementById('f_fork_hsc').value = bike ? (bike.fork_hsc_clicks ?? '') : '';
        document.getElementById('f_fork_lsc').value = bike ? (bike.fork_lsc_clicks ?? '') : '';
        document.getElementById('f_fork_hsr').value = bike ? (bike.fork_hsr_clicks ?? '') : '';
        document.getElementById('f_fork_lsr').value = bike ? (bike.fork_lsr_clicks ?? '') : '';
        document.getElementById('f_shock_brand').value = bike ? (bike.shock_brand || '') : '';
        document.getElementById('f_shock_model').value = bike ? (bike.shock_model || '') : '';
        document.getElementById('f_shock_travel').value = bike ? (bike.shock_travel_mm || '') : '';
        document.getElementById('f_shock_pressure').value = bike ? (bike.shock_pressure_psi || '') : '';
        document.getElementById('f_shock_rebound').value = bike ? (bike.shock_rebound_clicks ?? '') : '';
        document.getElementById('f_shock_compression').value = bike ? (bike.shock_compression_clicks ?? '') : '';
        document.getElementById('f_shock_sag').value = bike ? (bike.shock_sag_mm || '') : '';
        document.getElementById('f_shock_damper').value = bike ? (bike.shock_damper || '') : '';
        document.getElementById('f_shock_hsc').value = bike ? (bike.shock_hsc_clicks ?? '') : '';
        document.getElementById('f_shock_lsc').value = bike ? (bike.shock_lsc_clicks ?? '') : '';
        document.getElementById('f_shock_hsr').value = bike ? (bike.shock_hsr_clicks ?? '') : '';
        document.getElementById('f_shock_lsr').value = bike ? (bike.shock_lsr_clicks ?? '') : '';
        toggleForkDamper();
        toggleShockDamper();
        document.getElementById('f_groupset').value = bike ? (bike.groupset || '') : '';
        document.getElementById('f_brakes').value = bike ? (bike.brakes || '') : '';
        document.getElementById('f_rotor_front').value = bike ? (bike.rotor_size_front_mm || '') : '';
        document.getElementById('f_rotor_rear').value = bike ? (bike.rotor_size_rear_mm || '') : '';
        document.getElementById('f_handlebar_width').value = bike ? (bike.handlebar_width_mm || '') : '';
        document.getElementById('f_stem_length').value = bike ? (bike.stem_length_mm || '') : '';
        document.getElementById('f_dropper_travel').value = bike ? (bike.dropper_travel_mm || '') : '';

        toggleSuspensionSections();
        editingBikeId = bike ? bike.id : null;
        _formLoading = false;
        form.scrollIntoView({ behavior:'smooth' });
    }

    function toggleSuspensionSections() {
        var val = document.getElementById('f_suspension_type').value;
        document.getElementById('forkSection').style.display = (val === 'rigid') ? 'none' : 'block';
        document.getElementById('shockSection').style.display = (val === 'front_rear') ? 'block' : 'none';
    }
    document.getElementById('f_suspension_type').addEventListener('change', toggleSuspensionSections);

    var _formLoading = false;

    function toggleForkDamper() {
        var v = document.getElementById('f_fork_damper').value;
        var isFull = v === 'fox_grip2' || v === 'fox_grip_x2' || v === 'rs_vivid_ult';
        var isSimple = v === 'fox_grip_x' || v === 'fox_fit4' || v === 'rs_charger_2' || v === 'rs_charger_21' || v === 'rs_charger_3' || v === 'st_qlr';
        document.getElementById('forkDamperFull').style.display = isFull ? 'block' : 'none';
        document.getElementById('forkDamperSimple').style.display = isSimple ? 'block' : 'none';
        if (_formLoading) return;
        if (!isFull) { document.getElementById('f_fork_hsc').value = ''; document.getElementById('f_fork_lsc').value = ''; document.getElementById('f_fork_hsr').value = ''; document.getElementById('f_fork_lsr').value = ''; }
        if (!isSimple) { document.getElementById('f_fork_rebound').value = ''; document.getElementById('f_fork_compression').value = ''; }
    }

    function toggleShockDamper() {
        var v = document.getElementById('f_shock_damper').value;
        var isFull = v === 'fox_x2' || v === 'rs_sd_rc2t' || v === 'rs_vivid_ult';
        var isSimple = v === 'fox_dps' || v === 'rs_sd' || v === 'rs_vivid';
        document.getElementById('shockDamperFull').style.display = isFull ? 'block' : 'none';
        document.getElementById('shockDamperSimple').style.display = isSimple ? 'block' : 'none';
        if (_formLoading) return;
        if (!isFull) { document.getElementById('f_shock_hsc').value = ''; document.getElementById('f_shock_lsc').value = ''; document.getElementById('f_shock_hsr').value = ''; document.getElementById('f_shock_lsr').value = ''; }
        if (!isSimple) { document.getElementById('f_shock_rebound').value = ''; document.getElementById('f_shock_compression').value = ''; }
    }

    function loadBikes() {
        fetch('/api/user/bikes/full?_=' + Date.now(), { headers: { 'Authorization': 'Bearer ' + TOKEN } })
            .then(function(r){ return r.json(); })
            .then(function(data){
                bikes = data;
                renderBikeList();
            });
    }

    function renderBikeList() {
        var el = document.getElementById('bikeListContainer');
        if (!bikes.length) {
            el.innerHTML = '<div class="empty-state"><div class="big-icon">🚲</div><p>В гараже пока пусто. Добавьте свой первый байк!</p></div>';
            return;
        }
        var html = '<div class="bike-grid">';
        bikes.forEach(function(b){
            var typeBadge = 'badge-' + (b.bike_type || 'mtb');
            html += '<div class="bike-card" onclick="selectBike(' + b.id + ')">';
            html += '<h3>🚲 ' + escapeHtml(b.name || 'Байк #' + b.id) + '</h3>';
            html += '<div class="meta">' + (b.rider_weight_kg || '?') + ' кг · ' + (b.wheel_size || '29') + '"</div>';
            html += '<div class="tags"><span class="' + typeBadge + '">' + (b.bike_type || 'MTB') + '</span>';
            if (b.suspension_type) html += '<span>' + ({'front_rear':'2 подвески','front_only':'Вилка','rigid':'Жёсткая'}[b.suspension_type] || b.suspension_type) + '</span>';
            html += '</div></div>';
        });
        html += '</div>';
        el.innerHTML = html;
    }

    function collectForm() {
        function v(id) { var e = document.getElementById(id); if (!e) return null; return e.value; }
        function n(id) { var x = parseFloat(v(id)); return isNaN(x) ? null : x; }
        function i(id) { var x = parseInt(v(id), 10); return isNaN(x) ? null : x; }
        return {
            name: v('f_name'),
            bike_type: v('f_bike_type'),
            rider_weight_kg: n('f_rider_weight'),
            tire_type: v('f_tire_type'),
            tire_brand: v('f_tire_brand') || null,
            frame_material: v('f_frame_material') || null,
            wheel_size: v('f_wheel_size'),
            front_tire_width_mm: n('f_front_tire_width'),
            front_tire_pressure_psi: n('f_front_tire_pressure'),
            rear_tire_width_mm: n('f_rear_tire_width'),
            rear_tire_pressure_psi: n('f_rear_tire_pressure'),
            suspension_type: v('f_suspension_type'),
            fork_brand: v('f_fork_brand') || null,
            fork_model: v('f_fork_model') || null,
            fork_travel_mm: i('f_fork_travel'),
            fork_pressure_psi: n('f_fork_pressure'),
            fork_rebound_clicks: i('f_fork_rebound'),
            fork_compression_clicks: i('f_fork_compression'),
            fork_sag_mm: n('f_fork_sag'),
            fork_damper: v('f_fork_damper') || null,
            fork_hsc_clicks: i('f_fork_hsc'),
            fork_lsc_clicks: i('f_fork_lsc'),
            fork_hsr_clicks: i('f_fork_hsr'),
            fork_lsr_clicks: i('f_fork_lsr'),
            shock_brand: v('f_shock_brand') || null,
            shock_model: v('f_shock_model') || null,
            shock_travel_mm: i('f_shock_travel'),
            shock_pressure_psi: n('f_shock_pressure'),
            shock_rebound_clicks: i('f_shock_rebound'),
            shock_compression_clicks: i('f_shock_compression'),
            shock_sag_mm: n('f_shock_sag'),
            shock_damper: v('f_shock_damper') || null,
            shock_hsc_clicks: i('f_shock_hsc'),
            shock_lsc_clicks: i('f_shock_lsc'),
            shock_hsr_clicks: i('f_shock_hsr'),
            shock_lsr_clicks: i('f_shock_lsr'),
            groupset: v('f_groupset') || null,
            brakes: v('f_brakes') || null,
            rotor_size_front_mm: i('f_rotor_front'),
            rotor_size_rear_mm: i('f_rotor_rear'),
            handlebar_width_mm: i('f_handlebar_width'),
            stem_length_mm: i('f_stem_length'),
            dropper_travel_mm: i('f_dropper_travel'),
        };
    }

    document.getElementById('addBikeBtn').addEventListener('click', function(){
        editingBikeId = null;
        loadBikeForm(null);
    });

    document.getElementById('cancelBikeBtn').addEventListener('click', function(){
        document.getElementById('bikeForm').style.display = 'none';
    });

    document.getElementById('saveBikeBtn').addEventListener('click', async function(){
        var data = collectForm();
        if (!data.name) return alert('Введите название байка');
        var url = editingBikeId ? '/api/user/bikes/full/' + editingBikeId : '/api/user/bikes/full';
        var method = editingBikeId ? 'PUT' : 'POST';
        var r = await fetch(url, {
            method: method,
            headers: { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (r.ok) {
            if (window.umami) umami.track('bike_create', { bike_type: data.bike_type });
            document.getElementById('bikeForm').style.display = 'none';
            document.getElementById('bikeDashboard').style.display = 'none';
            document.getElementById('bikeListContainer').style.display = 'block';
            document.getElementById('addBikeBtn').style.display = 'block';
            loadBikes();
        } else {
            alert('Ошибка сохранения');
        }
    });

    window.deleteBike = async function(id) {
        if (!confirm('Удалить байк?')) return;
        var r = await fetch('/api/user/bikes/' + id, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + TOKEN } });
        if (r.ok) {
            if (window.umami) umami.track('bike_delete', { bike_id: id });
            document.getElementById('bikeDashboard').style.display = 'none';
            document.getElementById('bikeListContainer').style.display = 'block';
            document.getElementById('addBikeBtn').style.display = 'block';
            loadBikes();
        }
    };

    loadBikes();
    loadProfileSection();
    if (window.umami) umami.track('garage_view', { has_auth: !!TOKEN });
}
</script>
</body>
</html>"""

@router.get("/garage", response_class=HTMLResponse)
async def garage_page():
    return HTMLResponse(content=GARAGE_HTML)
