from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database.connection import get_connection
from api.dependencies import get_current_user
from typing import Optional

router = APIRouter()

class VoteRequest(BaseModel):
    vote: int = Field(..., ge=1, le=5)

@router.post("/api/vote/{park_id}")
async def vote(park_id: str, req: VoteRequest, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        # Проверяем существование парка
        park = conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")

        # INSERT OR REPLACE (требуется уникальный индекс)
        conn.execute(
            "INSERT OR REPLACE INTO soil_votes (user_id, park_id, vote) VALUES (?, ?, ?)",
            (user["user_id"], park_id, req.vote)
        )
        conn.commit()

        # Возвращаем новое среднее значение
        row = conn.execute(
            "SELECT AVG(vote) as avg, COUNT(*) as cnt FROM soil_votes WHERE park_id = ?",
            (park_id,)
        ).fetchone()
        return {"ok": True, "new_avg": round(row["avg"], 2), "vote_count": row["cnt"]}
    finally:
        conn.close()

@router.get("/api/votes")
async def get_votes(group_id: Optional[str] = None):
    """Возвращает агрегированные голоса по паркам группы (или всем). Без авторизации."""
    conn = get_connection()
    try:
        if group_id:
            parks = conn.execute("SELECT id FROM parks WHERE group_id = ?", (group_id,)).fetchall()
        else:
            parks = conn.execute("SELECT id FROM parks").fetchall()

        result = {}
        for p in parks:
            park_id = p["id"]
            row = conn.execute(
                "SELECT AVG(vote) as avg, COUNT(*) as cnt FROM soil_votes WHERE park_id = ?",
                (park_id,)
            ).fetchone()
            result[park_id] = {
                "avg": round(row["avg"], 2) if row["avg"] is not None else None,
                "count": row["cnt"]
            }
        return result
    finally:
        conn.close()

@router.get("/api/vote/my")
async def get_my_votes(user=Depends(get_current_user)):
    """Возвращает голоса текущего пользователя по всем паркам."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT park_id, vote FROM soil_votes WHERE user_id = ?", (user["user_id"],)
        ).fetchall()
        return {r["park_id"]: r["vote"] for r in rows}
    finally:
        conn.close()