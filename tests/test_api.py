def test_groups(client):
    r = client.get("/api/groups")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    ids = {g["id"] for g in data}
    assert ids == {"mtb_parks", "mtb_mountains", "pamps"}


def test_weather_group(client):
    r = client.get("/api/weather/mtb_parks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    for park in data:
        assert "name" in park["park"]
        assert "soilStatus" in park["park"]


def test_unknown_group(client):
    r = client.get("/api/weather/unknown")
    assert r.status_code == 200
    assert r.json() == {"error": "Группа не найдена"}


def test_park_status(client):
    r = client.get("/api/park/fili/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "dryHours" in data


def test_park_weather(client):
    r = client.get("/api/park/fili/weather?days=7")
    assert r.status_code == 200
    data = r.json()
    assert data["park_id"] == "fili"
    assert len(data["weather"]) == 7


def test_park_photos(client):
    r = client.get("/api/park/fili/photos")
    assert r.status_code == 200
    data = r.json()
    assert data["photos"] is not None
    assert isinstance(data["photos"], list)
    assert data["total"] >= 0


def test_unknown_park(client):
    r = client.get("/api/park/nonexistent/status")
    assert r.status_code == 404
    assert r.json() == {"error": "Парк не найден"}


def test_development_page(client):
    r = client.get("/development")
    assert r.status_code == 200
    assert "ИИ определяет" in r.text


def test_contacts_page(client):
    r = client.get("/contacts")
    assert r.status_code == 200
    assert "Контакт" in r.text or "email" in r.text or "@" in r.text


def test_admin_page(client):
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Админ" in r.text


def test_auth_bad_login(client):
    r = client.post("/api/auth/login", json={"email": "x@x.ru", "password": "wrong"})
    assert r.status_code == 401