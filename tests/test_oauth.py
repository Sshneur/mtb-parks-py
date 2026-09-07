import time as _time
from urllib.parse import parse_qs, urlparse

from database.connection import get_connection
from api import auth_routes as ar


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Заменяет httpx.AsyncClient: POST -> токен, GET -> профиль юзера."""

    def __init__(self, token_json, user_json):
        self.token_json = token_json
        self.user_json = user_json

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return _FakeResponse(200, self.token_json)

    async def get(self, *args, **kwargs):
        return _FakeResponse(200, self.user_json)


_YANDEX_TOKEN = {"access_token": "y0_test_token", "expires_in": 86400}
_YANDEX_USER = {
    "id": "123456789",
    "login": "ivanov.ilya",
    "display_name": "ilya_ivanov",
    "default_email": "ilya@example.com",
    "default_avatar_id": "12345/abcd",
}


def _fake_yandex_httpx(monkeypatch):
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *a, **k: _FakeAsyncClient(_YANDEX_TOKEN, _YANDEX_USER),
    )


def _redirect_loc(r):
    assert r.status_code in (302, 307)
    return r.headers["location"]


def test_yandex_login_redirect_to_authorize_with_state(client):
    r = client.get("/auth/yandex", follow_redirects=False)
    loc = _redirect_loc(r)
    assert loc.startswith("https://oauth.yandex.com/authorize?")
    assert parse_qs(urlparse(loc).query)["state"][0]


def test_yandex_callback_missing_state(client):
    r = client.get("/auth/yandex/callback?code=abc", follow_redirects=False)
    loc = _redirect_loc(r)
    assert loc == "/login?error=invalid_state"


def test_yandex_callback_wrong_state(client):
    r = client.get("/auth/yandex/callback?code=abc&state=wrongstate123", follow_redirects=False)
    assert _redirect_loc(r) == "/login?error=invalid_state"


def test_yandex_callback_error_param(client):
    r = client.get("/auth/yandex/callback?error=access_denied", follow_redirects=False)
    assert _redirect_loc(r) == "/login?error=access_denied"


def test_yandex_flow_ocode_and_consume(client, monkeypatch):
    _fake_yandex_httpx(monkeypatch)

    # 1. берем state со страницы входа
    r = client.get("/auth/yandex", follow_redirects=False)
    state = parse_qs(urlparse(_redirect_loc(r)).query)["state"][0]

    # 2. callback — в URL одноразовый код, НЕ токен
    r = client.get(f"/auth/yandex/callback?code=abc&state={state}", follow_redirects=False)
    ocode_loc = _redirect_loc(r)
    assert "/?ocode=" in ocode_loc
    assert "token=" not in ocode_loc
    ocode = urlparse(ocode_loc).query.split("=")[1]

    # 3. state израсходован
    assert state not in ar._oauth_states

    # 4. пользователь создан с OAuth-данными
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT email, username, oauth_provider, oauth_id, oauth_token FROM users WHERE email=?",
            ("ilya@example.com",),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["oauth_provider"] == "yandex"
    assert row["oauth_id"] == "123456789"
    assert row["oauth_token"] == "y0_test_token"
    assert row["username"] == "ilya_ivanov"

    # 5. обмен кода на токен — первый раз успех, токен рабочий
    r = client.post("/api/auth/oauth/consume", json={"code": ocode})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token
    me = client.get("/api/user/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200

    # 6. повторное использование кода запрещено
    r = client.post("/api/auth/oauth/consume", json={"code": ocode})
    assert r.status_code == 400


def test_consume_unknown_code(client):
    r = client.post("/api/auth/oauth/consume", json={"code": "invalidcode123"})
    assert r.status_code == 400


def test_consume_expired_code(client):
    ar._oauth_codes["expiredcode1"] = (1, _time.time() - 10)
    r = client.post("/api/auth/oauth/consume", json={"code": "expiredcode1"})
    assert r.status_code == 400
    assert "expiredcode1" not in ar._oauth_codes


def test_oauth_username_fallback(client):
    u = ar._find_or_create_oauth_user("yandex", "u1", "u1@example.com", "Илья Иванов")
    assert u is not None
    conn = get_connection()
    try:
        row = conn.execute("SELECT username FROM users WHERE id=?", (u["id"],)).fetchone()
    finally:
        conn.close()
    assert row["username"] == "yandex_u1"


def test_oauth_link_existing_email(client):
    email = "link@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "link_man"})
    u = ar._find_or_create_oauth_user("yandex", "link1", email, "Link", "http://a", "token1")
    assert u is not None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT oauth_provider, oauth_id, oauth_token, username FROM users WHERE id=?",
            (u["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row["oauth_provider"] == "yandex"
    assert row["oauth_id"] == "link1"
    assert row["oauth_token"] == "token1"
    assert row["username"] == "link_man"


def test_oauth_conflict_different_provider(client):
    email = "conf@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "conf_man"})
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET oauth_provider='vk', oauth_id='v1' WHERE email=?", (email,))
        conn.commit()
    finally:
        conn.close()
    u = ar._find_or_create_oauth_user("yandex", "y1", email, "Conf")
    assert u is None


def test_oauth_same_provider_relogin_updates_token(client):
    u1 = ar._find_or_create_oauth_user("yandex", "r1", "r1@example.com", "Rider", None, "tok1")
    u2 = ar._find_or_create_oauth_user("yandex", "r1", "r1@example.com", "Rider", None, "tok2")
    assert u1["id"] == u2["id"]
    conn = get_connection()
    try:
        row = conn.execute("SELECT oauth_token FROM users WHERE id=?", (u1["id"],)).fetchone()
    finally:
        conn.close()
    assert row["oauth_token"] == "tok2"


def test_login_error_displayed_in_human(client):
    r = client.get("/login?error=access_denied")
    assert r.status_code == 200
    assert "Вы не разрешили доступ к аккаунту." in r.text