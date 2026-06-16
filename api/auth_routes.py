from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from database.connection import get_connection
from api.limiter import limiter
import asyncio
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# HTML-шаблон страницы регистрации
REGISTER_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Регистрация — МТБ Парки 2.0</title>
    <link rel="stylesheet" href="/css/style.css">
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
    <title>Вход — МТБ Парки 2.0</title>
    <link rel="stylesheet" href="/css/style.css">
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
                window.location.href = '/';
            } else {
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
async def register(user: UserRegister):
    conn = get_connection()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        username_exists = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
        if username_exists:
            raise HTTPException(status_code=400, detail="Этот ник уже занят")

        hashed = pwd_context.hash(user.password)
        conn.execute("INSERT INTO users (email, password_hash, username) VALUES (?, ?, ?)",
                     (user.email, hashed, user.username))
        conn.commit()
        return {"ok": True, "message": "Регистрация успешна"}
    finally:
        conn.close()

@router.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(user: UserLogin, request: Request):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, password_hash, role, failed_attempts, locked_until, username FROM users WHERE email = ?",
            (user.email,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        if row["locked_until"]:
            locked_until = datetime.fromisoformat(row["locked_until"])
            if datetime.utcnow() < locked_until:
                raise HTTPException(status_code=403, detail="Аккаунт временно заблокирован. Попробуйте позже.")

        if not pwd_context.verify(user.password, row["password_hash"]):
            new_attempts = row["failed_attempts"] + 1
            if new_attempts >= 5:
                lock_time = datetime.utcnow() + timedelta(minutes=15)
                conn.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (new_attempts, lock_time.isoformat(), row["id"])
                )
            else:
                conn.execute(
                    "UPDATE users SET failed_attempts = ? WHERE id = ?",
                    (new_attempts, row["id"])
                )
            conn.commit()
            await asyncio.sleep(1)
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (row["id"],)
        )
        conn.commit()

        token = jwt.encode(
            {"user_id": row["id"], "email": row["email"], "role": row["role"], "username": row["username"],
             "exp": datetime.utcnow() + timedelta(days=7)},
            SECRET_KEY, algorithm=ALGORITHM
        )
        return {"ok": True, "token": token, "role": row["role"]}
    finally:
        conn.close()