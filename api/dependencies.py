from fastapi import Request, HTTPException
import jwt
from database.connection import get_connection
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM

async def get_current_user(request: Request):
    """Извлекает пользователя из JWT токена в заголовке Authorization"""
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
        row = conn.execute(
            "SELECT role FROM users WHERE id = ?", (payload.get("user_id"),)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    payload["role"] = row["role"]
    return payload  # содержит user_id, email, role