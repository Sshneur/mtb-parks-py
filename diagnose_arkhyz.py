from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation
from datetime import datetime, timezone

conn = get_connection()
rows = conn.execute("""
    SELECT * FROM weather_hourly
    WHERE park_id='arkhyz'
    ORDER BY timestamp ASC
""").fetchall()
conn.close()

total_rain = 0.0
total_evap = 0.0
cnt_with_hum = 0
cnt_all = len(rows)
W = 0.0
surf = {"z0m": 0.015, "d": 0.1, "r_s": 100}
forest_coef = 0.3

for r in rows:
    rain = r['rain'] or 0.0
    temp = r['temperature'] or 15.0
    wind = r['wind_speed'] or 0.0
    rad = r['radiation'] or 0.0
    rel_hum = r['relative_humidity']
    press = r['surface_pressure']

    if rel_hum is not None and press is not None:
        cnt_with_hum += 1

    if rain > 0:
        W = min(1.0, W + rain / 10)
        total_rain += rain
    else:
        if rel_hum is not None and press is not None:
            evap = calc_pm_evaporation(
                temp_c=temp, wind_speed=wind, radiation=rad,
                relative_humidity=rel_hum, pressure_pa=press * 100,
                z0m=surf["z0m"], d=surf["d"], r_s=surf["r_s"]
            ) * forest_coef
            total_evap += evap
            W = max(0.0, W - evap)

print(f"Всего записей: {cnt_all}")
print(f"Из них с влажностью/давлением: {cnt_with_hum}")
print(f"Суммарный дождь: {total_rain:.1f} мм")
print(f"Суммарное испарение (ПМ): {total_evap:.1f} мм")
print(f"Итоговая влажность W: {W:.3f}")