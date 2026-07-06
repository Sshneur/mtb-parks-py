from database.connection import get_connection
from services.penman_monteith import calc_pm_evaporation

# Параметры старой модели для loam (как в soil_calculator.py)
SOIL_COEFFICIENTS = {
    "loam": {"k_t": 0.08, "k_w": 0.06, "k_r": 0.001, "k_s": 0.04},
}

conn = get_connection()
# Берём один час с дождём для Чесс Парка (или любого другого)
row = conn.execute("""
    SELECT timestamp, rain, temperature, wind_speed, radiation, relative_humidity, surface_pressure
    FROM weather_hourly
    WHERE park_id='chess' AND rain > 0
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

    # Старая модель (испарение при отсутствии дождя)
    soil = SOIL_COEFFICIENTS["loam"]
    forest_coef = 0.1  # как у Чесс Парка
    # Формула старой модели:
    f_T = 0.05 * max(row['temperature'], 0)
    g_v = 0.03 * row['wind_speed']
    g_r = 0.001 * row['radiation']
    old_evap = forest_coef * (soil['k_t'] * f_T + soil['k_w'] * g_v + soil['k_r'] * g_r + soil['k_s'])
    print(f"\nСтарая модель: испарение = {old_evap:.6f} (условные единицы)")
    print(f"  При дожде {row['rain']:.1f} мм, W увеличилось бы на {row['rain']/10:.3f}")

    # Новая модель (ПМ)
    surf = {"z0m": 0.5, "d": 1.5, "r_s": 300}  # clay_heavy
    pm_evap = calc_pm_evaporation(
        temp_c=row['temperature'],
        wind_speed=row['wind_speed'],
        radiation=row['radiation'],
        relative_humidity=row['relative_humidity'],
        pressure_pa=row['surface_pressure'] * 100,  # гПа -> Па
        z0m=surf['z0m'],
        d=surf['d'],
        r_s=surf['r_s']
    )
    pm_evap_with_forest = pm_evap * forest_coef
    print(f"Новая модель (ПМ): чистое испарение = {pm_evap:.6f} мм/час")
    print(f"  С учётом леса (×{forest_coef}): {pm_evap_with_forest:.6f} мм/час")
    print(f"  В единицах W (÷10): {pm_evap_with_forest/10:.6f}")
else:
    print("Нет данных")