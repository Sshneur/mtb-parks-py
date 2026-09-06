from datetime import datetime, timedelta, timezone

import pytest

from services.soil_calculator import (
    _get,
    calculate_green_days,
    calculate_soil_moisture_from_db,
    get_soil_status,
)

PARK_LOAM = {"soil_type": "loam", "forest_coef": 0.3}


def _hour(offset_h, temp=20, wind=3, rad=500, rain=0.0):
    ts = datetime.now(timezone.utc) - timedelta(hours=offset_h)
    return {
        "timestamp": ts.isoformat(),
        "temperature": temp,
        "wind_speed": wind,
        "radiation": rad,
        "rain": rain,
    }


def test_get_helper_zero_is_not_none():
    hour = {"temperature": 0, "wind_speed": 0, "radiation": 0, "rain": 0}
    assert _get(hour, "temperature", 15) == 0
    assert _get(hour, "wind_speed", 5) == 0
    assert _get(hour, "radiation", 9) == 0
    assert _get(hour, "rain", 1) == 0
    assert _get(hour, "nope", 7) == 7
    assert _get({}, "temperature", 15) == 15


def test_moisture_10_dry_hours_no_rain():
    data = [_hour(i, temp=20, wind=3, rad=500) for i in range(10, 0, -1)]
    result = calculate_soil_moisture_from_db(PARK_LOAM, data)
    # Без дождя W = 0, dry_hours = 0
    assert result["current_moisture"] == 0
    assert result["dry_hours"] == 0
    assert result["hours_since_rain"] is None


def test_moisture_rain_then_drying():
    # 5 мм дождя = 0.5 единицы W
    data = [_hour(2, rain=5.0), _hour(1, rain=0.0)]
    result = calculate_soil_moisture_from_db(PARK_LOAM, data)
    assert result["current_moisture"] > 0
    assert result["total_rain"] == 5.0
    assert result["hours_since_rain"] is not None
    assert result["evaporation_rate"] > 0


def test_green_days_structure():
    data = []
    for i in range(72, 0, -1):
        h = _hour(i, temp=22, wind=2, rad=600)
        h["rain"] = 8.0 if i <= 36 else 0.0
        data.append(h)
    days = calculate_green_days(PARK_LOAM, data, "2026-08")
    assert isinstance(days, list)
    assert len(days) >= 28
    assert {"date", "W", "status", "label"} <= set(days[0])
    statuses = {d["status"] for d in days}
    assert statuses <= {"dry", "wet", "bog", "no_data"}


@pytest.mark.parametrize(
    "rain_total,dry_hours,hours_since,is_asphalt,expected",
    [
        (10, 100, 200, False, "Болото 🟤"),
        (10, 30, 200, False, "Мокро 💧"),
        (0, 7, 200, False, "Альденте 🌵"),
        (0, 0, 200, False, "Бетон 🪨"),
        (0, 0, 100, False, "Сухо ✅"),
        (0, 0, None, True, "Сухо ✅"),
        (0, 0, 100, True, "Сухо ✅"),
        (5, 0, 0, False, "Сухо ✅"),
    ],
)
def test_soil_status_matrix(rain_total, dry_hours, hours_since, is_asphalt, expected):
    assert get_soil_status(rain_total, dry_hours, hours_since, is_asphalt) == expected