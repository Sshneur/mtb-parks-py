from fastapi import Request
from database.connection import get_connection
import jwt
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM
import asyncio
import logging

logger = logging.getLogger(__name__)

LOG_SKIP_PREFIXES = (
    "/css", "/js", "/lib", "/photos", "/icons", "/favicon",
    "/manifest.json", "/sw.js", "/og-image",
    "/x.js", "/api/x",
)

_write_counter = {"n": 0}


def _write_log(user_id, path, ip):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO request_log (user_id, endpoint, ip) VALUES (?, ?, ?)",
            (user_id, path, ip)
        )
        conn.commit()
        _write_counter["n"] += 1
        if _write_counter["n"] % 500 == 0:
            conn.execute("DELETE FROM request_log WHERE created_at < datetime('now', '-30 days')")
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
    response.headers["Referrer-Policy"] = "no-referrer"
    path = request.url.path
    if not path.startswith(LOG_SKIP_PREFIXES):
        asyncio.create_task(asyncio.to_thread(
            _write_log,
            user_id,
            path,
            request.client.host if request.client else None,
        ))
    return response