def _register(client, email, username="u"):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "username": username})
    assert r.status_code == 200, r.text
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return login.json()["token"]


def test_catalog_13_parks(client):
    r = client.get("/api/parks/catalog")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 13
    keys = {"parkId", "name", "group_id", "group_name", "lat", "lon", "soilStatus"}
    assert all(keys.issubset(p) for p in data)
    # первые 4 парка каталога — Фили, Ерино, Чесс, Козловка (стартовая по умолчанию)
    assert [p["parkId"] for p in data[:4]] == ["fili", "erino", "chess", "kozlovka"]


def test_park_list_still_works(client):
    r = client.get("/api/park/list")
    assert r.status_code == 200
    assert len(r.json()) == 13


def test_start_parks_default_and_save(client):
    token = _register(client, "start1@t.ru", "start1")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/user/start-parks", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False
    assert data["parks"] == [
        {"park_id": "fili"}, {"park_id": "erino"},
        {"park_id": "chess"}, {"park_id": "kozlovka"},
    ]

    r = client.post("/api/user/start-parks", json={"park_ids": ["krylatskoye", "fili"]}, headers=headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["added"] is True

    r = client.get("/api/user/start-parks", headers=headers)
    assert r.json()["configured"] is True
    assert r.json()["parks"] == [
        {"park_id": "krylatskoye"}, {"park_id": "fili"},
    ]

    # повторное сохранение того же набора — added=False
    r = client.post("/api/user/start-parks", json={"park_ids": ["krylatskoye", "fili"]}, headers=headers)
    assert r.json()["added"] is False


def test_start_parks_isolation(client):
    t1 = _register(client, "iso1@t.ru", "iso1")
    t2 = _register(client, "iso2@t.ru", "iso2")
    client.post("/api/user/start-parks", json={"park_ids": ["erino"]}, headers={"Authorization": f"Bearer {t1}"})
    r1 = client.get("/api/user/start-parks", headers={"Authorization": f"Bearer {t1}"}).json()
    r2 = client.get("/api/user/start-parks", headers={"Authorization": f"Bearer {t2}"}).json()
    assert r1["parks"] == [{"park_id": "erino"}]
    assert r2["configured"] is False  # второй пользователь не затронут


def test_start_parks_cannot_use_unknown_park(client):
    token = _register(client, "startbad@t.ru", "startbad")
    r = client.post(
        "/api/user/start-parks",
        json={"park_ids": ["nope"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_start_parks_empty_selection(client):
    token = _register(client, "startempty@t.ru", "startempty")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/user/start-parks", json={"park_ids": []}, headers=headers)
    assert r.status_code == 200
    data = client.get("/api/user/start-parks", headers=headers).json()
    assert data["configured"] is True
    assert data["parks"] == []


def test_start_parks_delete_resets(client):
    token = _register(client, "startdel@t.ru", "startdel")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/user/start-parks", json={"park_ids": ["erino"]}, headers=headers)
    r = client.delete("/api/user/start-parks", headers=headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    data = client.get("/api/user/start-parks", headers=headers).json()
    assert data["configured"] is False
    assert len(data["parks"]) == 4


def test_park_request_create_201(client):
    r = client.post("/api/park/requests", json={
        "name": "Новый Тестовый Парк",
        "lat": 55.5,
        "lon": 37.5,
        "soil_description": "Суглинок, торф",
        "storm_drain": "",
        "contact_tg": "@vasya",
        "tg_group": "",
        "trails_count": 3,
        "description": "Свежие трассы",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["ok"] is True
    assert data["id"] >= 1
    assert client.get("/api/park/requests").status_code == 404  # публичного списка нет


def test_park_request_duplicate_409(client):
    client.post("/api/park/requests", json={"name": "Дубль Парк", "lat": 55.5, "lon": 37.5})
    r = client.post("/api/park/requests", json={"name": "Дубль Парк", "lat": 55.6, "lon": 37.6})
    assert r.status_code == 409
    assert r.json()["detail"] == "Парк с таким названием уже существует"


def test_park_request_duplicate_with_existing_park_409(client):
    r = client.post("/api/park/requests", json={"name": "Парк Фили", "lat": 55.7, "lon": 37.4})
    assert r.status_code == 409


def _make_admin(client, email):
    token = _register(client, email, email.split("@")[0])
    from database.connection import get_connection
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()
    return token


def test_admin_approve_creates_park(client):
    atoken = _make_admin(client, "adm_appr@t.ru")
    r = client.post("/api/park/requests", json={
        "name": "Одобряемый Парк",
        "lat": 55.1,
        "lon": 37.1,
        "soil_description": "Глинистый грунт",
        "storm_drain": "частично",
        "tg_group": "mypark_chat",
        "trails_count": 4,
        "description": "Описание",
    })
    req_id = r.json()["id"]

    h = {"Authorization": f"Bearer {atoken}"}
    r = client.post(
        f"/api/admin/park-requests/{req_id}/approve",
        json={"group_id": "mtb_parks", "soil_type": "clay", "forest_coef": 0.25, "dry_hours_default": 72},
        headers=h,
    )
    assert r.status_code == 200
    park_id = r.json()["park_id"]

    from database.connection import get_connection
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM parks WHERE id = ?", (park_id,)).fetchone()
        assert row is not None
        assert row["name"] == "Одобряемый Парк"
        assert row["soil_type"] == "clay"
        assert row["storm_drain"] == "частично"
        assert row["tg_group"] == "mypark_chat"
        assert row["group_id"] == "mtb_parks"
        # заявка закрыта
        st = conn.execute("SELECT status FROM park_requests WHERE id = ?", (req_id,)).fetchone()
        assert st["status"] == "approved"
    finally:
        conn.close()

    # повторное одобрение — 400
    r = client.post(
        f"/api/admin/park-requests/{req_id}/approve",
        json={"group_id": "mtb_parks"},
        headers=h,
    )
    assert r.status_code == 400


def test_admin_approve_translit_suffix(client):
    atoken = _make_admin(client, "adm_appr2@t.ru")
    h = {"Authorization": f"Bearer {atoken}"}
    # Два разных названия, но с одинаковым транслитом: "Финишный Парк" и "Финишный-парк"
    for name in ("Финишный Парк", "Финишный-парк"):
        r = client.post("/api/park/requests", json={"name": name, "lat": 55.0, "lon": 37.0})
        req_id = r.json()["id"]
        res = client.post(f"/api/admin/park-requests/{req_id}/approve", json={"group_id": "mtb_parks"}, headers=h)
        assert res.status_code == 200, res.text
    # коллизия id при транслите решается суффиксом _2
    conn = None
    from database.connection import get_connection
    conn = get_connection()
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM parks WHERE name IN ('Финишный Парк', 'Финишный-парк')"
        ).fetchall()]
    finally:
        conn.close()
    assert "finishnyy-park" in ids
    assert "finishnyy-park_2" in ids


def test_admin_reject(client):
    atoken = _make_admin(client, "adm_rej@t.ru")
    h = {"Authorization": f"Bearer {atoken}"}
    r = client.post("/api/park/requests", json={"name": "Отклоняемый Парк", "lat": 55.0, "lon": 37.0})
    req_id = r.json()["id"]
    assert client.post(f"/api/admin/park-requests/{req_id}/reject", headers=h).status_code == 200
    assert client.get("/api/admin/park-requests?status=rejected", headers=h).json()[0]["id"] == req_id
    assert client.post(f"/api/admin/park-requests/{req_id}/reject", headers=h).status_code == 400
    assert client.post("/api/admin/park-requests/999999/reject", headers=h).status_code == 404


def test_admin_requests_requires_admin(client):
    token = _register(client, "plain_req@t.ru", "plainreq")
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/park-requests", headers=h).status_code == 403
    assert client.post("/api/admin/park-requests/1/approve", json={}, headers=h).status_code == 403


def test_park_page_shows_storm_drain_and_tg(client):
    from database.connection import get_connection
    conn = get_connection()
    try:
        conn.execute("UPDATE parks SET storm_drain = 'частично', tg_group = 'fili_group' WHERE id = 'fili'")
        conn.commit()
    finally:
        conn.close()
    r = client.get("/park/fili")
    assert r.status_code == 200
    assert "Ливневки" in r.text
    assert "частично" in r.text
    assert "Telegram-группа" in r.text
    assert "https://t.me/fili_group" in r.text


def test_guess_soil_type():
    from services.park_requests import guess_soil_type
    assert guess_soil_type("глинистый грунт, торф") == "clay"
    assert guess_soil_type("чернозём") == "chernozem"
    assert guess_soil_type("супесь") == "sand"
    assert guess_soil_type("песчаная почва") == "sand"
    assert guess_soil_type("подзолистая почва") == "podzol"
    assert guess_soil_type("асфальтовое покрытие") == "asphalt"
    assert guess_soil_type("суглинок") == "loam"
    assert guess_soil_type("непонятно что") == "loam"


def test_translit_id():
    from services.park_requests import translit_id
    assert translit_id("Парк Фили") == "park-fili"
    assert translit_id("Памп Трек Фукусима") == "pamp-trek-fukusima"
    assert translit_id("Ерино") == "erino"
    assert translit_id("???") == "park"