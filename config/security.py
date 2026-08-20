import os

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET не задан или короче 32 символов. "
        "Задайте переменную окружения JWT_SECRET перед запуском."
    )

ALGORITHM = "HS256"