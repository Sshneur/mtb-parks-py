import time


def test_register_success(client):
    r = client.post("/api/auth/register", json={
        "email": f"reg_{int(time.time())}@t.ru",
        "password": "password123",
        "username": "rider1",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_register_duplicate_email_409(client):
    email = f"dup_{int(time.time())}@t.ru"
    first = client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "r1"})
    assert first.status_code == 200
    second = client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "r2"})
    assert second.status_code == 409
    assert "заняты" in second.json()["detail"]


def test_login_success_returns_token(client):
    email = f"log_{int(time.time())}@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "rider"})
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["token"]


def test_login_wrong_password_401(client):
    email = f"bad_{int(time.time())}@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "r"})
    r = client.post("/api/auth/login", json={"email": email, "password": "wrongpass"})
    assert r.status_code == 401


def test_refresh_issues_token(client):
    email = f"ref_{int(time.time())}@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "rider"})
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["token"]
    r = client.get("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["token"]


def test_refresh_invalid_token_401(client):
    r = client.get("/api/auth/refresh", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401