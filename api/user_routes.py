from fastapi import APIRouter, Depends, HTTPException
from database.connection import get_connection
from api.dependencies import get_current_user

router = APIRouter()

@router.get("/api/user/me")
async def get_me(user=Depends(get_current_user)):
    """Возвращает информацию о текущем пользователе"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, email, role FROM users WHERE id = ?", (user["user_id"],)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return {"id": row["id"], "email": row["email"], "role": row["role"]}
    finally:
        conn.close()

@router.get("/api/user/favorites")
async def get_favorites(user=Depends(get_current_user)):
    """Возвращает список избранных парков пользователя"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT p.id, p.name, p.group_id, p.lat, p.lon
            FROM favorite_parks fp
            JOIN parks p ON fp.park_id = p.id
            WHERE fp.user_id = ?
        """, (user["user_id"],)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.post("/api/user/favorites/{park_id}")
async def add_favorite(park_id: str, user=Depends(get_current_user)):
    """Добавляет парк в избранное"""
    conn = get_connection()
    try:
        # Проверим, существует ли парк
        park = conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")
        conn.execute(
            "INSERT OR IGNORE INTO favorite_parks (user_id, park_id) VALUES (?, ?)",
            (user["user_id"], park_id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@router.delete("/api/user/favorites/{park_id}")
async def remove_favorite(park_id: str, user=Depends(get_current_user)):
    """Удаляет парк из избранного"""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM favorite_parks WHERE user_id = ? AND park_id = ?",
            (user["user_id"], park_id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()