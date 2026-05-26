from fastapi import APIRouter, Depends, HTTPException
from database.connection import get_connection
from api.dependencies import get_current_user

router = APIRouter()

@router.get("/api/user/me")
async def get_me(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, email, username, role FROM users WHERE id = ?", (user["user_id"],)).fetchone()
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

# ... (остальные эндпоинты для избранного без изменений)