import math

def calc_pm_evaporation(
    temp_c: float,          # температура воздуха, °C
    wind_speed: float,      # скорость ветра на высоте 2 м, м/с
    radiation: float,       # солнечная радиация (shortwave), Вт/м²
    relative_humidity: float, # относительная влажность, %
    pressure_pa: float,     # атмосферное давление, Па
    z0m: float = 0.015,     # шероховатость для импульса, м
    d: float = 0.1,         # высота смещения, м
    r_s: float = 100.0      # поверхностное сопротивление, с/м
) -> float:
    """
    Возвращает эталонную эвапотранспирацию ET0 (мм/час)
    по уравнению FAO‑56 Пенмана‑Монтейта для часового шага.
    """

    # Константы
    LAMBDA = 2.45          # скрытая теплота парообразования, МДж/кг
    CP = 0.001013          # удельная теплоёмкость воздуха, МДж/(кг·°C)
    RHO_A = 1.225          # плотность воздуха, кг/м³

    # --- 1. Переводим радиацию из Вт/м² в МДж/(м²·час) ---
    R_n = radiation * 0.0036   # МДж/(м²·час)

    # --- 2. Давление насыщенного пара (es) и фактическое (ea), кПа ---
    es = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * relative_humidity / 100.0
    vpd = es - ea                     # дефицит давления пара, кПа
    if vpd < 0:
        vpd = 0.0

    # --- 3. Наклон кривой давления насыщенного пара (Δ), кПа/°C ---
    delta = 4098 * es / (temp_c + 237.3) ** 2

    # --- 4. Психрометрическая константа (γ), кПа/°C ---
    P_kpa = pressure_pa / 1000.0
    gamma = 0.00163 * P_kpa / LAMBDA

    # --- 5. Аэродинамическое сопротивление и проводимость ---
    if wind_speed > 0:
        ra = 208.0 / wind_speed
    else:
        ra = 9999.0
    g_a = 1.0 / ra

    # --- 6. Уравнение Пенмана‑Монтейта (часовое) ---
    numerator = (delta * R_n) + (RHO_A * CP * vpd * g_a)
    denominator = LAMBDA * (delta + gamma * (1 + g_a * r_s))

    if denominator == 0:
        return 0.0

    et0_kg_per_m2s = numerator / denominator
    et0_mm_per_hour = et0_kg_per_m2s * 3600.0 / 1000.0

    return max(0.0, et0_mm_per_hour)