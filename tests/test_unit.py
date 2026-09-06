from datetime import datetime, timezone

from api.utils import parse_time, to_msk, weather_code
from services.soil_calculator import get_soil_status
from services.penman_monteith import wind_to_2m


def test_utils_parse_time():
    dt = parse_time("2024-01-15T10:30:00Z")
    assert dt.tzinfo is not None
    assert dt.hour == 10
    msk = to_msk(dt)
    assert "+03:00" in msk
    assert weather_code(30, 0) == 1
    assert weather_code(10, 5) == 63
    assert weather_code(10, 0) == 3
    assert weather_code(0, 0) == 3
    assert weather_code(None, 0) == 3
    assert weather_code(20, 0.7) == 61


def test_soil_status_concrete_requires_dry():
    assert get_soil_status(0, 0, 200) == "Бетон 🪨"
    assert get_soil_status(0, 7.3, 200) == "Альденте 🌵"
    assert get_soil_status(0, 100, 200) == "Болото 🟤"
    assert get_soil_status(0, 30, 200) == "Мокро 💧"
    assert get_soil_status(0, 0, 100) == "Сухо ✅"


def test_wind_to_2m():
    assert wind_to_2m(0) == 0.0
    assert wind_to_2m(None) == 0.0
    assert 7.0 < wind_to_2m(10) < 8.0