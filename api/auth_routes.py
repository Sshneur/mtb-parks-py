from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
import jwt
import sqlite3
from datetime import datetime, timedelta, timezone
from database.connection import get_connection
from api.limiter import limiter
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM
import asyncio
import os
import bcrypt
from passlib.hash import sha256_crypt
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str):
    try:
        if bcrypt.checkpw(password.encode(), password_hash.encode()):
            return True, False
    except ValueError:
        pass
    try:
        if sha256_crypt.verify(password, password_hash):
            return True, True
    except Exception as e:
        logger.error(f"Ошибка проверки старого хеша: {e}")
    return False, False


_login_failures: dict[str, list[float]] = {}

# IP из X-Forwarded-For используется только при TRUSTED_PROXY=true (прод за
# nginx, который ПЕРЕЗАПИСЫВАЕТ заголовок $remote_addr); иначе — реальный peer,
# чтобы клиент не мог спуфить первый XFF и обходить блокировку.
def _ip_key(request: Request) -> str:
    if os.getenv("TRUSTED_PROXY", "false").lower() == "true":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ip_blocked(ip: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    failures = [t for t in _login_failures.get(ip, []) if now - t < 900]
    _login_failures[ip] = failures
    return len(failures) >= 10


def _record_failure(ip: str):
    _login_failures.setdefault(ip, []).append(datetime.now(timezone.utc).timestamp())


def _clear_failures(ip: str):
    _login_failures.pop(ip, None)


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен быть не короче 8 символов")
        return v

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Пароль не должен превышать 128 символов")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def login_password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Пароль не должен превышать 128 символов")
        return v

# HTML-шаблон страницы регистрации
REGISTER_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Регистрация — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <style>
        .auth-container {
            max-width: 400px;
            margin: 80px auto;
            padding: 30px;
            background: rgba(18, 22, 30, 0.9);
            border: 1px solid rgba(74, 144, 226, 0.25);
            border-radius: 12px;
            text-align: center;
            color: #ddd;
        }
        .auth-container h1 {
            margin-bottom: 20px;
            color: #74a8e2;
        }
        .auth-container input {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            border: 1px solid rgba(74, 144, 226, 0.25);
            border-radius: 8px;
            background: rgba(18, 22, 30, 0.7);
            color: #ddd;
            font-size: 16px;
            box-sizing: border-box;
        }
        .auth-container button {
            width: 100%;
            padding: 12px;
            margin-top: 15px;
            background: #4caf50;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }
        .auth-container button:hover {
            background: #388e3c;
        }
        .auth-container .links {
            margin-top: 15px;
            font-size: 14px;
        }
        .auth-container .links a {
            color: #74a8e2;
            text-decoration: none;
        }
        .error {
            color: #e74c3c;
            margin-top: 10px;
        }
    </style>
    <script defer src="https://stats.gripcheck.ru/x.js" data-website-id="WEBSITE_ID" data-domains="gripcheck.ru,xn--80afdaebh7a3c.xn--p1ai" data-do-not-track="true"></script>
</head>
<body>
    <div class="auth-container">
        <h1>Регистрация</h1>
        <form id="registerForm">
            <input type="text" id="username" placeholder="Никнейм" required>
            <input type="email" id="email" placeholder="Email" required>
            <input type="password" id="password" placeholder="Пароль" required>
            <button type="submit">Зарегистрироваться</button>
        </form>
        <div class="error" id="error"></div>
        <div class="links">
            Уже есть аккаунт? <a href="/login">Войти</a>
        </div>
    </div>
    <script>
        document.getElementById('registerForm').onsubmit = async function(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password, username})
            });
            const data = await res.json();
            if (data.ok) {
                if (window.umami) umami.track('registration');
                window.location.href = '/login?registered=1';
            } else {
                document.getElementById('error').textContent = data.detail || 'Ошибка регистрации';
            }
        };
    </script>
</body>
</html>
"""

# HTML-шаблон страницы входа
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход — Что с грунтом?</title>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <style>
        .auth-container {
            max-width: 400px;
            margin: 80px auto;
            padding: 30px;
            background: rgba(18, 22, 30, 0.9);
            border: 1px solid rgba(74, 144, 226, 0.25);
            border-radius: 12px;
            text-align: center;
            color: #ddd;
        }
        .auth-container h1 {
            margin-bottom: 20px;
            color: #74a8e2;
        }
        .auth-container input {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            border: 1px solid rgba(74, 144, 226, 0.25);
            border-radius: 8px;
            background: rgba(18, 22, 30, 0.7);
            color: #ddd;
            font-size: 16px;
            box-sizing: border-box;
        }
        .auth-container button {
            width: 100%;
            padding: 12px;
            margin-top: 15px;
            background: #4caf50;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }
        .auth-container button:hover {
            background: #388e3c;
        }
        .auth-container .links {
            margin-top: 15px;
            font-size: 14px;
        }
        .auth-container .links a {
            color: #74a8e2;
            text-decoration: none;
        }
        .error {
            color: #e74c3c;
            margin-top: 10px;
        }
    </style>
    <script defer src="https://stats.gripcheck.ru/x.js" data-website-id="WEBSITE_ID" data-domains="gripcheck.ru,xn--80afdaebh7a3c.xn--p1ai" data-do-not-track="true"></script>
</head>
<body>
    <div class="auth-container">
        <h1>Вход</h1>
        <form id="loginForm">
            <input type="email" id="email" placeholder="Email" required>
            <input type="password" id="password" placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
        <div class="error" id="error"></div>
        <div class="links">
            Нет аккаунта? <a href="/register">Зарегистрироваться</a>
        </div>
        <div class="links">
            <a href="/">← На главную</a>
        </div>
    </div>
    <script>
        document.getElementById('loginForm').onsubmit = async function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password})
            });
            const data = await res.json();
            if (data.ok) {
                localStorage.setItem('token', data.token);
                if (window.umami) umami.track('login');
                window.location.href = '/';
            } else {
                if (window.umami) umami.track('login_failure', { error: data.detail || 'unknown' });
                document.getElementById('error').textContent = data.detail || 'Ошибка входа';
            }
        };
    </script>
</body>
</html>
"""

@router.get("/register", response_class=HTMLResponse)
async def register_page():
    return HTMLResponse(content=REGISTER_HTML)

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(content=LOGIN_HTML)

@router.post("/api/auth/register")
@limiter.limit("10/hour")
async def register(user: UserRegister, request: Request):
    conn = get_connection()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Email или ник уже заняты")
        username_exists = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
        if username_exists:
            raise HTTPException(status_code=400, detail="Email или ник уже заняты")

        hashed = hash_password(user.password)
        try:
            conn.execute("INSERT INTO users (email, password_hash, username) VALUES (?, ?, ?)",
                         (user.email, hashed, user.username))
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email или ник уже заняты")
        return {"ok": True, "message": "Регистрация успешна"}
    finally:
        conn.close()

@router.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(user: UserLogin, request: Request):
    ip = _ip_key(request)
    if _ip_blocked(ip):
        raise HTTPException(status_code=429, detail="Слишком много попыток входа. Попробуйте позже.")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, password_hash, role, failed_attempts, username FROM users WHERE email = ?",
            (user.email,)
        ).fetchone()
        if not row:
            _record_failure(ip)
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        verified, needs_rehash = verify_password(user.password, row["password_hash"])
        if not verified:
            new_attempts = row["failed_attempts"] + 1
            conn.execute(
                "UPDATE users SET failed_attempts = ? WHERE id = ?",
                (new_attempts, row["id"])
            )
            conn.commit()
            _record_failure(ip)
            await asyncio.sleep(1)
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        if needs_rehash:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(user.password), row["id"])
            )
        conn.execute(
            "UPDATE users SET failed_attempts = 0 WHERE id = ?",
            (row["id"],)
        )
        conn.commit()
        _clear_failures(ip)

        token = jwt.encode(
            {"user_id": row["id"], "email": row["email"], "role": row["role"], "username": row["username"],
             "exp": datetime.now(timezone.utc) + timedelta(days=30)},
            SECRET_KEY, algorithm=ALGORITHM
        )
        return {"ok": True, "token": token, "role": row["role"]}
    finally:
        conn.close()

@router.get("/api/auth/refresh")
async def refresh_token(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")
    conn = get_connection()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (payload.get("user_id"),)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Пользователь не найден")
    finally:
        conn.close()
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    if datetime.now(timezone.utc) + timedelta(days=15) > exp:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(days=30)
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"ok": True, "token": token}