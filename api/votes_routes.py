from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database.connection import get_connection
from api.dependencies import get_current_user
from api.utils import get_reset_time_msk, get_park_vote_stats
from typing import Optional
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class VoteRequest(BaseModel):
    vote: int = Field(..., ge=1, le=5)

@router.post("/api/vote/{park_id}")
async def vote(park_id: str, req: VoteRequest, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        park = conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")

        conn.execute(
            "INSERT OR REPLACE INTO soil_votes (user_id, park_id, vote) VALUES (?, ?, ?)",
            (user["user_id"], park_id, req.vote)
        )
        conn.commit()

        row = conn.execute(
            "SELECT AVG(vote) as avg, COUNT(*) as cnt FROM park_photos WHERE park_id = ? AND status = 'approved'",
            (park_id,)
        ).fetchone()
        return {"ok": True, "new_avg": round(row["avg"], 2) if row["avg"] else None, "vote_count": row["cnt"] or 0}
    except Exception as e:
        logger.error(f"Ошибка голосования: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка")
    finally:
        conn.close()

@router.get("/api/votes")
async def get_votes(group_id: Optional[str] = None):
    conn = get_connection()
    try:
        if group_id:
            parks = conn.execute("SELECT id FROM parks WHERE group_id = ?", (group_id,)).fetchall()
        else:
            parks = conn.execute("SELECT id FROM parks").fetchall()

        reset_time_utc = get_reset_time_msk()

        result = {}
        for p in parks:
            result[p["id"]] = get_park_vote_stats(conn, p["id"], reset_time_utc)

        return result
    except Exception as e:
        logger.error(f"Ошибка в /api/votes: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка")
    finally:
        conn.close()

@router.get("/api/vote/my")
async def get_my_votes(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT park_id, vote FROM soil_votes WHERE user_id = ?", (user["user_id"],)
        ).fetchall()
        return {r["park_id"]: r["vote"] for r in rows}
    finally:
        conn.close()