from fastapi import APIRouter, HTTPException, Request
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
    username: str   # новое поле

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/api/auth/register")
async def register(user: UserRegister):
    conn = get_connection()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        # проверяем уникальность ника
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