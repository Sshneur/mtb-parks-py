from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation

conn = get_connection()

# 1. Проверяем текущий forest_coef
row = conn.execute("SELECT id, forest_coef FROM parks WHERE id='chess'").fetchone()
print(f"Текущий forest_coef в БД: {row['forest_coef']}")

# 2. Берём последний час с данными
row = conn.execute("""
    SELECT temperature, wind_speed, radiation, relative_humidity, surface_pressure
    FROM weather_hourly
    WHERE park_id='chess'
    ORDER BY timestamp DESC
    LIMIT 1
""").fetchone()
conn.close()

if row and row['relative_humidity'] is not None and row['surface_pressure'] is not None:
    print(f"Температура: {row['temperature']}°C")
    print(f"Ветер: {row['wind_speed']} м/с")
    print(f"Радиация: {row['radiation']} Вт/м²")
    print(f"Влажность: {row['relative_humidity']}%")
    print(f"Давление: {row['surface_pressure']} гПа")

    surf = {'z0m': 0.5, 'd': 1.5, 'r_s': 200}
    evap = calc_pm_evaporation(
        temp_c=row['temperature'],
        wind_speed=row['wind_speed'],
        radiation=row['radiation'],
        relative_humidity=row['relative_humidity'],
        pressure_pa=row['surface_pressure'] * 100,
        z0m=surf['z0m'],
        d=surf['d'],
        r_s=surf['r_s']
    )
    print(f"\nЧистое испарение ПМ: {evap:.6f} мм/час")
    print(f"При forest_coef=0.1: {evap * 0.1:.6f} мм/час")
    print(f"При forest_coef=0.2: {evap * 0.2:.6f} мм/час")
else:
    print("Нет полных данных для последнего часа")