from fastapi import Request
from database.connection import get_connection
from jose import jwt
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM
import asyncio
import logging

logger = logging.getLogger(__name__)


def _write_log(user_id, path, ip):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO request_log (user_id, endpoint, ip) VALUES (?, ?, ?)",
            (user_id, path, ip)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось записать лог запроса: {e}")
    finally:
        conn.close()


async def log_request(request: Request, call_next):
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
        except Exception as e:
            logger.error(f"Ошибка декодирования токена в middleware: {e}")

    response = await call_next(request)
    await asyncio.to_thread(
        _write_log,
        user_id,
        request.url.path,
        request.client.host if request.client else None,
    )
    return response