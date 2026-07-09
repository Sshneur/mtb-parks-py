from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database.connection import get_connection
from api.dependencies import get_current_user
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ===== ФУНКЦИЯ ДЛЯ ОПРЕДЕЛЕНИЯ ВРЕМЕНИ СБРОСА (4:00 МСК) =====
def get_reset_time_msk():
    now_msk = datetime.now(timezone.utc) + timedelta(hours=3)
    if now_msk.hour >= 4:
        reset_msk = now_msk.replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        reset_msk = (now_msk - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    reset_utc = reset_msk - timedelta(hours=3)
    return reset_utc

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
        raise HTTPException(status_code=500, detail=str(e))
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
        reset_time_str = reset_time_utc.strftime("%Y-%m-%d %H:%M:%S")
        rain_period_start = (reset_time_utc - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        result = {}
        for p in parks:
            park_id = p["id"]

            # Проверяем дождь в период перед сбросом
            rain_rows = conn.execute("""
                SELECT COUNT(*) as cnt FROM weather_hourly
                WHERE park_id = ? AND rain > 0
                  AND datetime(timestamp) >= datetime(?) AND datetime(timestamp) < datetime(?)
            """, (park_id, rain_period_start, reset_time_str)).fetchone()

            rain_reset = False
            avg = None
            count = 0

            if rain_rows and rain_rows["cnt"] > 0:
                rain_reset = True
                row = conn.execute("""
                    SELECT AVG(vote) as avg, COUNT(*) as cnt
                    FROM park_photos
                    WHERE park_id = ? AND status = 'approved' AND datetime(created_at) > datetime(?)
                """, (park_id, reset_time_str)).fetchone()
                if row and row["cnt"] > 0:
                    avg = round(row["avg"], 2)
                    count = row["cnt"]
                else:
                    avg = None
                    count = 0
            else:
                row = conn.execute("""
                    SELECT AVG(vote) as avg, COUNT(*) as cnt
                    FROM park_photos
                    WHERE park_id = ? AND status = 'approved'
                """, (park_id,)).fetchone()
                avg = round(row["avg"], 2) if row["avg"] is not None else None
                count = row["cnt"] or 0

            result[park_id] = {
                "avg": avg,
                "count": count,
                "rain_reset": rain_reset
            }

        return result
    except Exception as e:
        logger.error(f"Ошибка в /api/votes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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