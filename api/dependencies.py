from fastapi import Request, HTTPException
from jose import jwt
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM

async def get_current_user(request: Request):
    """Извлекает пользователя из JWT токена в заголовке Authorization"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # содержит user_id, email, role
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")