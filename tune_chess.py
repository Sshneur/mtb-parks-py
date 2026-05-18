from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation

conn = get_connection()
rows = conn.execute("""
    SELECT * FROM weather_hourly
    WHERE park_id='chess'
    ORDER BY timestamp ASC
""").fetchall()
conn.close()

# Фиксируем z0m и d (как в SURFACE_PARAMS), меняем r_s и forest_coef
z0m = 0.5
d = 1.5
print("r_s\tforest_coef\tW")
for r_s in [200, 300, 400, 500]:
    for forest_coef in [0.08, 0.1, 0.12, 0.15]:
        W = 0.0
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
                    z0m=z0m, d=d, r_s=r_s
                )
                # Применяем лесной коэффициент и переводим в единицы W (как в API)
                W = max(0.0, W - evap * forest_coef / 10.0)
        print(f"{r_s}\t{forest_coef:.2f}\t\t{W:.3f}")