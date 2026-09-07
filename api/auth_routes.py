from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
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
import httpx
import secrets
import re
import time
import urllib.parse

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
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')

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
    def login_password_min_length(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("Пароль не может быть пустым")
        return v

    @field_validator("password")
    @classmethod
    def login_password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Пароль не должен превышать 128 символов")
        return v

class OAuthConsumeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=64)

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
    <script defer src="https://gripcheck.ru/x.js" data-website-id="b88aec0e-21c1-445a-9ce2-566959574f4f" data-domains="gripcheck.ru,xn--80afdaebh7a3c.xn--p1ai" data-do-not-track="true"></script>
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
        .oauth-divider {
            display: flex;
            align-items: center;
            margin: 18px 0 12px;
            color: #666;
            font-size: 13px;
        }
        .oauth-divider::before, .oauth-divider::after {
            content: '';
            flex: 1;
            border-bottom: 1px solid rgba(74, 144, 226, 0.15);
        }
        .oauth-divider span { padding: 0 12px; }
        .oauth-buttons {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .oauth-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 12px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            border: 1px solid;
        }
        .oauth-btn:active { transform: scale(0.98); }
        .oauth-icon { width: 22px; height: 22px; flex-shrink: 0; }
        .oauth-yandex {
            background: rgba(252, 63, 29, 0.12);
            border-color: rgba(252, 63, 29, 0.3);
            color: #fc3f1d;
        }
        .oauth-yandex:hover { background: rgba(252, 63, 29, 0.22); }
        .oauth-vk {
            background: rgba(76, 117, 163, 0.12);
            border-color: rgba(76, 117, 163, 0.3);
            color: #4c75a3;
        }
        .oauth-vk:hover { background: rgba(76, 117, 163, 0.22); }
    </style>
    <script defer src="https://gripcheck.ru/x.js" data-website-id="b88aec0e-21c1-445a-9ce2-566959574f4f" data-domains="gripcheck.ru,xn--80afdaebh7a3c.xn--p1ai" data-do-not-track="true"></script>
</head>
<body>
    <div class="auth-container">
        <h1>Вход</h1>
        <form id="loginForm">
            <input type="email" id="email" placeholder="Email" required>
            <input type="password" id="password" placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
        <div class="oauth-buttons">
            <a href="/auth/yandex" class="oauth-btn oauth-yandex">
                <svg class="oauth-icon" viewBox="0 0 24 24"><path d="M12.19 2C6.59 2 2 6.49 2 12.09c0 5.6 4.59 10.09 10.19 10.09 5.6 0 10.19-4.49 10.19-10.09C22.38 6.49 17.79 2 12.19 2zm4.73 14.06c-.18.32-.59.43-.91.24-2.49-1.52-5.63-1.87-9.33-1.02-.36.08-.71-.14-.79-.5-.08-.36.14-.71.5-.79 4.07-.93 7.54-.53 10.39 1.22.32.19.42.59.23.91zm1.27-2.83c-.23.38-.71.5-1.09.26-2.85-1.75-7.19-2.25-10.54-1.23-.42.13-.86-.11-.99-.53-.13-.42.11-.86.53-.99 3.89-1.18 8.7-.62 12.01 1.42.38.23.5.71.26 1.09zm.11-2.95C15.14 8.72 9.29 8.51 5.77 9.56c-.5.15-1.03-.14-1.18-.64-.15-.5.14-1.03.64-1.18 4.09-1.24 10.72-1.01 14.9 1.49.46.28.61.88.33 1.34-.28.46-.88.61-1.34.33z" fill="#FC3F1D"/></svg>
                Войти через Яндекс
            </a>
        </div>
        <div class="error" id="error"></div>
        <div class="links">
            Нет аккаунта? <a href="/register">Зарегистрироваться</a>
        </div>
        <div class="links">
            <a href="/">← На главную</a>
        </div>
    </div>
    <script>
        (function() {
            const err = new URLSearchParams(location.search).get('error');
            if (!err) return;
            const messages = {
                no_code: 'Вход не выполнен: отсутствует код авторизации. Попробуйте ещё раз.',
                token_exchange_failed: 'Не удалось обменять код на токен. Попробуйте ещё раз.',
                user_info_failed: 'Не удалось получить данные профиля. Попробуйте ещё раз.',
                invalid_state: 'Произошёл сбой безопасности при входе. Попробуйте ещё раз.',
                account_linked: 'Эта почта уже привязана к другой учётной записи соцсети.',
                access_denied: 'Вы не разрешили доступ к аккаунту.',
                oauth_not_configured: 'Вход через соцсеть временно недоступен.',
                vk_not_configured: 'Вход через ВК временно недоступен.',
                oauth_consume_failed: 'Не удалось завершить вход. Попробуйте ещё раз.'
            };
            document.getElementById('error').textContent = messages[err] || 'Ошибка входа: ' + err;
        })();
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
                const n = new URLSearchParams(location.search).get('next');
                window.location.href = (n && n.startsWith('/') && !n.startsWith('//')) ? n : '/';
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
            raise HTTPException(status_code=409, detail="Email или ник уже заняты")
        username_exists = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
        if username_exists:
            raise HTTPException(status_code=409, detail="Email или ник уже заняты")

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


# ==================== OAuth ====================

# Одноразовые коды для передачи токена клиенту (жизнь ~90с, одноразовые)
_OAUTH_CODE_TTL = 90
# Валидация state (CSRF): TTL 10 минут
_OAUTH_STATE_TTL = 600

_oauth_codes: dict[str, tuple[int, float]] = {}  # code -> (user_id, expires)
_oauth_states: dict[str, float] = {}             # state -> expires

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,30}$")


def _normalize_username(raw, provider: str, provider_id: str) -> str:
    if raw and _USERNAME_RE.match(raw):
        return raw
    return f"{provider}_{provider_id}"


def _issue_oauth_code(user_id: int) -> str:
    code = secrets.token_urlsafe(9)
    _oauth_codes[code] = (user_id, time.time() + _OAUTH_CODE_TTL)
    return code


def generate_token(user_id, email, role, username):
    return jwt.encode(
        {"user_id": user_id, "email": email, "role": role, "username": username,
         "exp": datetime.now(timezone.utc) + timedelta(days=30)},
        SECRET_KEY, algorithm=ALGORITHM
    )


def _find_or_create_oauth_user(provider: str, provider_id: str, email: str, username: str,
                               avatar_url: str = None, oauth_token: str = None):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id, email, role, username FROM users WHERE oauth_provider=? AND oauth_id=?",
            (provider, provider_id)
        ).fetchone()

        if user:
            updates = []
            params = []
            if oauth_token:
                updates.append("oauth_token=?")
                params.append(oauth_token)
            if avatar_url:
                updates.append("avatar=COALESCE(avatar,?)")
                params.append(avatar_url)
            if updates:
                params.append(user["id"])
                conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", params)
                conn.commit()
            return user

        existing = conn.execute("SELECT id, oauth_provider FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            if existing["oauth_provider"] and existing["oauth_provider"] != provider:
                return None  # аккаунт уже привязан к другой соцсети — не перезаписываем
            try:
                conn.execute(
                    "UPDATE users SET oauth_provider=?, oauth_id=?, oauth_token=?, avatar=COALESCE(avatar,?) WHERE id=?",
                    (provider, provider_id, oauth_token, avatar_url, existing["id"])
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return None
            return conn.execute("SELECT id, email, role, username FROM users WHERE id=?", (existing["id"],)).fetchone()

        username = _normalize_username(username, provider, provider_id)
        candidates = [username, f"{username}_{secrets.token_hex(2)}", f"{username}_{secrets.token_hex(4)}"]
        for candidate in candidates:
            try:
                cur = conn.execute(
                    "INSERT INTO users (email, username, oauth_provider, oauth_id, avatar, password_hash, oauth_token) "
                    "VALUES (?, ?, ?, ?, ?, '', ?)",
                    (email, candidate, provider, provider_id, avatar_url, oauth_token)
                )
                conn.commit()
                return conn.execute("SELECT id, email, role, username FROM users WHERE id=?",
                                    (cur.lastrowid,)).fetchone()
            except sqlite3.IntegrityError:
                continue  # email/username заняты — пробуем следующий кандидат либо отдаём None
        return None
    finally:
        conn.close()


@router.get("/auth/yandex")
async def yandex_login():
    from config.oauth import YA_CLIENT_ID, YA_REDIRECT_URI
    if not YA_CLIENT_ID:
        return RedirectResponse(url="/login?error=oauth_not_configured")
    state = secrets.token_hex(16)
    _oauth_states[state] = time.time() + _OAUTH_STATE_TTL
    auth_url = (
        f"https://oauth.yandex.com/authorize?"
        f"response_type=code&client_id={YA_CLIENT_ID}"
        f"&redirect_uri={YA_REDIRECT_URI}"
        f"&scope=login:info+login:email+login:avatar+login:login"
        f"&force_confirm=yes&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/auth/yandex/callback")
async def yandex_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return RedirectResponse(url=f"/login?error={urllib.parse.quote(error)}")
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    if not state or _oauth_states.get(state, 0) < time.time():
        return RedirectResponse(url="/login?error=invalid_state")
    _oauth_states.pop(state, None)

    from config.oauth import YA_CLIENT_ID, YA_CLIENT_SECRET

    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth.yandex.com/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": YA_CLIENT_ID,
            "client_secret": YA_CLIENT_SECRET,
        })
    if token_resp.status_code != 200:
        return RedirectResponse(url="/login?error=token_exchange_failed")
    token_data = token_resp.json()
    access_token = token_data["access_token"]

    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://login.yandex.ru/info?format=json",
            headers={"Authorization": f"OAuth {access_token}"}
        )
    if user_resp.status_code != 200:
        return RedirectResponse(url="/login?error=user_info_failed")
    yandex_user = user_resp.json()

    oauth_id = str(yandex_user["id"])
    email = yandex_user.get("default_email", f"yandex_{oauth_id}@oauth.local")
    username = yandex_user.get("display_name", yandex_user.get("login", f"yandex_{oauth_id}"))
    avatar_id = yandex_user.get("default_avatar_id", "")
    avatar_url = f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200" if avatar_id else None

    user = _find_or_create_oauth_user("yandex", oauth_id, email, username, avatar_url, access_token)
    if not user:
        return RedirectResponse(url="/login?error=account_linked")
    return RedirectResponse(url=f"/?ocode={_issue_oauth_code(user['id'])}")


@router.post("/api/auth/oauth/consume")
@limiter.limit("30/minute")
async def oauth_consume(req: OAuthConsumeRequest, request: Request):
    entry = _oauth_codes.get(req.code)
    if not entry:
        raise HTTPException(status_code=400, detail="Код недействителен")
    user_id, expires = entry
    _oauth_codes.pop(req.code, None)  # одноразовый код
    if expires < time.time():
        raise HTTPException(status_code=400, detail="Код истёк")
    conn = get_connection()
    try:
        user = conn.execute("SELECT id, email, role, username FROM users WHERE id=?", (user_id,)).fetchone()
    finally:
        conn.close()
    if not user:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    token = generate_token(user["id"], user["email"], user["role"], user["username"])
    return {"ok": True, "token": token}


@router.get("/auth/vk")
async def vk_login():
    from config.oauth import VK_APP_ID, VK_REDIRECT_URI, VK_API_VERSION
    if not VK_APP_ID:
        return RedirectResponse(url="/login?error=vk_not_configured")
    state = secrets.token_hex(16)
    _oauth_states[state] = time.time() + _OAUTH_STATE_TTL
    auth_url = (
        f"https://oauth.vk.com/authorize?"
        f"client_id={VK_APP_ID}&display=page"
        f"&redirect_uri={VK_REDIRECT_URI}"
        f"&scope=email,offline&response_type=code"
        f"&v={VK_API_VERSION}&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/auth/vk/callback")
async def vk_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return RedirectResponse(url=f"/login?error={urllib.parse.quote(error)}")
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    if not state or _oauth_states.get(state, 0) < time.time():
        return RedirectResponse(url="/login?error=invalid_state")
    _oauth_states.pop(state, None)

    from config.oauth import VK_APP_ID, VK_SECRET_KEY, VK_REDIRECT_URI, VK_API_VERSION
    if not VK_APP_ID or not VK_SECRET_KEY:
        return RedirectResponse(url="/login?error=vk_not_configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.get("https://oauth.vk.com/access_token", params={
            "client_id": VK_APP_ID,
            "client_secret": VK_SECRET_KEY,
            "redirect_uri": VK_REDIRECT_URI,
            "code": code,
        })
    if token_resp.status_code != 200:
        return RedirectResponse(url="/login?error=token_exchange_failed")
    token_data = token_resp.json()
    access_token = token_data["access_token"]
    vk_user_id = str(token_data["user_id"])
    vk_email = token_data.get("email", "")

    async with httpx.AsyncClient() as client:
        profile_resp = await client.get("https://api.vk.com/method/users.get", params={
            "user_ids": vk_user_id,
            "fields": "photo_200",
            "access_token": access_token,
            "v": VK_API_VERSION,
        })
    profile_data = profile_resp.json().get("response", [{}])[0]
    first_name = profile_data.get("first_name", "")
    last_name = profile_data.get("last_name", "")
    username = f"{first_name} {last_name}".strip() or f"vk_{vk_user_id}"
    avatar_url = profile_data.get("photo_200")

    email = vk_email or f"vk_{vk_user_id}@oauth.local"

    user = _find_or_create_oauth_user("vk", vk_user_id, email, username, avatar_url, access_token)
    if not user:
        return RedirectResponse(url="/login?error=account_linked")
    return RedirectResponse(url=f"/?ocode={_issue_oauth_code(user['id'])}")