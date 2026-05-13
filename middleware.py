from fastapi import Request
from database.connection import get_connection
from jose import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"

async def log_request(request: Request, call_next):
    # Попытаемся извлечь user_id из токена
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
        except:
            pass

    response = await call_next(request)

    # Пишем лог в БД
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO request_log (user_id, endpoint, ip) VALUES (?, ?, ?)",
            (user_id, request.url.path, request.client.host if request.client else None)
        )
        conn.commit()
    except:
        pass
    finally:
        conn.close()

    return response