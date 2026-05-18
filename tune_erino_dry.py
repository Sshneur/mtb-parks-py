from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation
from datetime import datetime, timezone

conn = get_connection()
rows = conn.execute("""
    SELECT * FROM weather_hourly
    WHERE park_id='erino'
    ORDER BY timestamp ASC
""").fetchall()
conn.close()

surf = {"z0m": 0.015, "d": 0.1, "r_s": 200}  # текущее значение для loam
now_utc = datetime.now(timezone.utc)

print("forest_coef\tW\tdry_hours (ожидаемое)")
for coef in [0.10, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18, 0.20]:
    W = 0.0
    recent_evaps = []
    for hour in rows:
        rain = hour['rain'] or 0.0
        if rain > 0:
            W = min(1.0, W + rain / 10.0)
        else:
            temp = hour['temperature'] or 15.0
            wind = hour['wind_speed'] or 0.0
            rad = hour['radiation'] or 0.0
            rel_hum = hour['relative_humidity'] or 70.0
            press = hour['surface_pressure'] or 1013.0
            evap = calc_pm_evaporation(
                temp_c=temp, wind_speed=wind, radiation=rad,
                relative_humidity=rel_hum, pressure_pa=press * 100.0,
                z0m=surf["z0m"], d=surf["d"], r_s=surf["r_s"]
            ) * coef
            W = max(0.0, W - evap / 10.0)
            
            # собираем испарения за последние 24 часа для расчёта dry_hours
            ts = datetime.fromisoformat(hour['timestamp'].replace("Z", "+00:00"))
            if (now_utc - ts.replace(tzinfo=timezone.utc)).total_seconds() <= 86400:
                recent_evaps.append(evap)
    
    if recent_evaps:
        avg_evap = sum(recent_evaps) / len(recent_evaps)
    else:
        avg_evap = 0.001
    dry_hours = W / (avg_evap / 10) if avg_evap > 0 else 0
    print(f"{coef:.2f}\t\t{W:.3f}\t{dry_hours:.1f}")