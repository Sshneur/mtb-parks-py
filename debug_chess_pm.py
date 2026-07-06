from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation
from datetime import datetime, timezone

park_id = 'chess'
forest_coef = 0.225
surf = {"z0m": 0.5, "d": 1.5, "r_s": 300}   # clay_heavy
now_utc = datetime.now(timezone.utc)

conn = get_connection()
# Берем данные начиная с 21 мая (дата сухости)
rows = conn.execute("""
    SELECT * FROM weather_hourly
    WHERE park_id = ? AND timestamp >= '2026-05-21'
    ORDER BY timestamp ASC
""", (park_id,)).fetchall()
conn.close()

if not rows:
    print("Нет данных после 21 мая")
    exit()

W = 0.0
total_rain = 0.0
last_rain_time = None
recent_evaps = []

for hour in rows:
    timestamp = datetime.fromisoformat(hour['timestamp'].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    temp = hour['temperature'] or 15
    wind = hour['wind_speed'] or 0
    rad = hour['radiation'] or 0
    rain = hour['rain'] or 0
    rel_hum = hour['relative_humidity'] or 70.0
    press = hour['surface_pressure'] or 1013.0

    if rain > 0:
        W = min(1.0, W + rain / 10)
        total_rain += rain
        last_rain_time = timestamp
    else:
        evap = calc_pm_evaporation(
            temp_c=temp, wind_speed=wind, radiation=rad,
            relative_humidity=rel_hum, pressure_pa=press * 100,
            z0m=surf["z0m"], d=surf["d"], r_s=surf["r_s"]
        ) * forest_coef
        W = max(0.0, W - evap / 10)
    
    # Для dry_hours: собираем испарение за последние 24 часа (только дневные часы)
    if (now_utc - timestamp).total_seconds() <= 86400:
        hour_utc = timestamp.hour
        rad_val = hour['radiation'] or 0
        if rad_val > 10 or (6 <= hour_utc <= 20):
            recent_evaps.append(evap)

print(f"Коэффициент: {forest_coef}")
print(f"Всего записей после 21 мая: {len(rows)}")
print(f"Суммарный дождь: {total_rain:.1f} мм")
print(f"Конечная влажность W: {W:.3f}")

if recent_evaps:
    avg_evap = sum(recent_evaps) / len(recent_evaps)
    print(f"Среднее испарение (дневные часы за 24ч): {avg_evap:.6f} мм/час")
    dry_hours = W / (avg_evap / 10) if avg_evap > 0 else 0
else:
    avg_evap = 0.001
    dry_hours = 0

print(f"dry_hours: {dry_hours:.1f} часов ({dry_hours/24:.1f} дней)")