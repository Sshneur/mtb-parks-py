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
    assert len(data) == 8
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
    assert "Контакты" in r.text


def test_admin_page(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/login" in r.headers.get("location", "")

def test_admin_page_200_for_admin(client):
    from database.connection import get_connection
    email = "adm_pg_test@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "adm_test"})
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["token"]
    r = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "Админ" in r.text


def test_umami_stats_days_param(client):
    from database.connection import get_connection
    from unittest.mock import patch

    email = "adm_stat_days@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "adm_sd"})
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.admin_routes._umami_get", return_value=[]), \
         patch("api.admin_routes._umami_login", return_value="test-token"):
        r = client.get("/api/admin/umami/stats?days=7", headers=headers)
        assert r.status_code == 200
        assert r.json()["days"] == 7

    r = client.get("/api/admin/umami/stats?days=15", headers=headers)
    assert r.status_code == 400

    with patch("api.admin_routes._umami_get", return_value=[]), \
         patch("api.admin_routes._umami_login", return_value="test-token"):
        r = client.get("/api/admin/umami/stats", headers=headers)
        assert r.status_code == 200
        assert r.json()["days"] == 30


def test_auth_bad_login(client):
    r = client.post("/api/auth/login", json={"email": "x@x.ru", "password": "wrong"})
    assert r.status_code == 401