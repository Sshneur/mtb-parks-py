from services.penman_monteith import calc_pm_evaporation, wind_to_2m


def test_et0_grows_with_vpd():
    et0_dry_air = calc_pm_evaporation(
        temp_c=20, wind_speed=3, radiation=200,
        relative_humidity=50, pressure_pa=1013 * 100
    )
    et0_humid_air = calc_pm_evaporation(
        temp_c=20, wind_speed=3, radiation=200,
        relative_humidity=90, pressure_pa=1013 * 100
    )
    assert et0_dry_air > et0_humid_air > 0


def test_aero_term_significant():
    et0_rad200 = calc_pm_evaporation(
        temp_c=20, wind_speed=3, radiation=200,
        relative_humidity=50, pressure_pa=1013 * 100
    )
    et0_rad0 = calc_pm_evaporation(
        temp_c=20, wind_speed=3, radiation=0,
        relative_humidity=50, pressure_pa=1013 * 100
    )
    assert et0_rad0 > 0.05
    assert et0_rad200 > et0_rad0 * 2


def test_et0_non_negative():
    et0 = calc_pm_evaporation(
        temp_c=-5, wind_speed=0, radiation=0,
        relative_humidity=100, pressure_pa=1013 * 100
    )
    assert et0 >= 0


def test_wind_to_2m():
    assert wind_to_2m(0) == 0.0
    assert wind_to_2m(None) == 0.0
    assert 7.0 < wind_to_2m(10) < 8.0
    assert wind_to_2m(3) < 3