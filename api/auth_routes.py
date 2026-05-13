from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from database.connection import get_connection
import os

router = APIRouter()

# Используем sha256_crypt – работает на всех платформах
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"

class UserRegister(BaseModel):
    email: EmailStr
    password: str

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

        hashed = pwd_context.hash(user.password)
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (user.email, hashed))
        conn.commit()
        return {"ok": True, "message": "Регистрация успешна"}
    finally:
        conn.close()

@router.post("/api/auth/login")
async def login(user: UserLogin):
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, email, password_hash, role FROM users WHERE email = ?", (user.email,)).fetchone()
        if not row or not pwd_context.verify(user.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        token = jwt.encode(
            {"user_id": row["id"], "email": row["email"], "role": row["role"],
             "exp": datetime.utcnow() + timedelta(days=7)},
            SECRET_KEY, algorithm=ALGORITHM
        )
        return {"ok": True, "token": token, "role": row["role"]}
    finally:
        conn.close()