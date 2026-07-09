from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from database.connection import get_connection
from api.limiter import limiter
from api.dependencies import get_current_user
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

# HTML-шаблоны регистрации и входа (опущены для краткости, но они есть)
REGISTER_HTML = """..."""  # оставьте свой, или используйте полный из предыдущих версий
LOGIN_HTML = """..."""     # аналогично

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
        conn.execute(
            "INSERT INTO users (email, password_hash, username) VALUES (?, ?, ?)",
            (user.email, hashed, user.username)
        )
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
            {
                "user_id": row["id"],
                "email": row["email"],
                "role": row["role"],
                "username": row["username"],
                "exp": datetime.utcnow() + timedelta(days=7)
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        return {"ok": True, "token": token, "role": row["role"]}
    finally:
        conn.close()

@router.get("/api/user/me")
async def get_me(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, username, role FROM users WHERE id = ?",
            (user["user_id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "role": row["role"]
        }
    finally:
        conn.close()

@router.get("/api/user/favorites")
async def get_favorites(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT park_id FROM favorite_parks WHERE user_id = ?",
            (user["user_id"],)
        ).fetchall()
        return [{"id": r["park_id"]} for r in rows]
    finally:
        conn.close()

@router.post("/api/user/favorites/{park_id}")
async def add_favorite(park_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        park = conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")
        conn.execute(
            "INSERT OR IGNORE INTO favorite_parks (user_id, park_id) VALUES (?, ?)",
            (user["user_id"], park_id)
        )
        conn.commit()
        return {"ok": True, "message": "Парк добавлен в избранное"}
    finally:
        conn.close()

@router.delete("/api/user/favorites/{park_id}")
async def remove_favorite(park_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM favorite_parks WHERE user_id = ? AND park_id = ?",
            (user["user_id"], park_id)
        )
        conn.commit()
        return {"ok": True, "message": "Парк удалён из избранного"}
    finally:
        conn.close()

# НОВЫЙ ЭНДПОИНТ ДЛЯ СТАТИСТИКИ ПОЛЬЗОВАТЕЛЯ
@router.get("/api/user/stats")
async def get_user_stats(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_votes_count, role FROM users WHERE id = ?",
            (user["user_id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        photo_votes_count = row["photo_votes_count"] or 0
        level = (photo_votes_count // 10) + 1
        return {
            "photo_votes_count": photo_votes_count,
            "level": level,
            "role": row["role"]
        }
    finally:
        conn.close()