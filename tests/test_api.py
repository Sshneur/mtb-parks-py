from fastapi.testclient import TestClient
from main import app
from database.connection import init_db, get_connection

client = TestClient(app)


def setup_module():
    init_db()


def test_groups():
    r = client.get("/api/groups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    ids = {g["id"] for g in data}
    assert ids == {"mtb_parks", "mtb_mountains", "pamps"}


def test_weather_group():
    r = client.get("/api/weather/mtb_parks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    for park in data:
        assert "name" in park["park"]
        assert "soilStatus" in park["park"]


def test_unknown_group():
    r = client.get("/api/weather/unknown")
    assert r.status_code == 200
    assert r.json() == {"error": "Группа не найдена"}


def test_park_status():
    r = client.get("/api/park/fili/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "dryHours" in data


def test_park_weather():
    r = client.get("/api/park/fili/weather?days=7")
    assert r.status_code == 200
    data = r.json()
    assert data["park_id"] == "fili"
    assert len(data["weather"]) == 7


def test_park_photos():
    r = client.get("/api/park/fili/photos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unknown_park():
    r = client.get("/api/park/nonexistent/status")
    assert r.status_code == 404
    assert r.json() == {"error": "Парк не найден"}


def test_development_page():
    r = client.get("/development")
    assert r.status_code == 200
    assert "ИИ определяет" in r.text


def test_contacts_page():
    r = client.get("/contacts")
    assert r.status_code == 200


def test_admin_page():
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Админ" in r.text


def test_auth_bad_login():
    r = client.post("/api/auth/login", json={"email": "x@x.ru", "password": "wrong"})
    assert r.status_code == 401


def test_utils_parse_time():
    from api.utils import parse_time, to_msk, weather_code
    from datetime import datetime, timezone
    dt = parse_time("2024-01-15T10:30:00Z")
    assert dt.tzinfo is not None
    assert dt.hour == 10
    msk = to_msk(dt)
    assert "+03:00" in msk
    assert weather_code(30, 0) == 1
    assert weather_code(10, 5) == 63
    assert weather_code(10, 0) == 3
