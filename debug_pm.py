from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation

conn = get_connection()
# Берём один час с дождём для Архыза
row = conn.execute("""
    SELECT timestamp, rain, temperature, wind_speed, radiation, relative_humidity, surface_pressure
    FROM weather_hourly
    WHERE park_id='arkhyz' AND rain > 0
    ORDER BY timestamp DESC
    LIMIT 1
""").fetchone()
conn.close()

if row:
    print("Данные из БД:")
    print(f"  Время: {row['timestamp']}")
    print(f"  Дождь: {row['rain']} мм")
    print(f"  Температура: {row['temperature']} °C")
    print(f"  Ветер: {row['wind_speed']} м/с")
    print(f"  Радиация: {row['radiation']} Вт/м²")
    print(f"  Влажность: {row['relative_humidity']} %")
    print(f"  Давление: {row['surface_pressure']} гПа")

    # Параметры для loam (как в SURFACE_PARAMS)
    z0m = 0.015
    d = 0.1
    r_s = 100
    forest_coef = 0.3

    evap = calc_pm_evaporation(
        temp_c=row['temperature'],
        wind_speed=row['wind_speed'],
        radiation=row['radiation'],
        relative_humidity=row['relative_humidity'],
        pressure_pa=row['surface_pressure'] * 100,  # гПа -> Па
        z0m=z0m,
        d=d,
        r_s=r_s
    )
    print(f"\nИспарение (чистая ПМ): {evap:.6f} мм/час")
    evap *= forest_coef
    print(f"Испарение с учётом леса (×0.3): {evap:.6f} мм/час")
    print(f"Дождь добавляет: {row['rain'] / 10:.3f} единиц влажности")
else:
    print("Нет данных")