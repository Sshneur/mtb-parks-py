from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from database.connection import get_connection
from api.dependencies import get_current_user
from typing import Optional, List
from database.models import PARKS
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/user/me")
async def get_me(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, username, role FROM users WHERE id = ?",
            (user["user_id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "role": row["role"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в get_me: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

# НОВЫЙ ЭНДПОИНТ ДЛЯ СТАТИСТИКИ ПОЛЬЗОВАТЕЛЯ
@router.get("/api/user/stats")
async def get_user_stats(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT photo_votes_count, role FROM users WHERE id = ?",
            (user["user_id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        photo_votes_count = row["photo_votes_count"] or 0
        level = (photo_votes_count // 10) + 1
        return {
            "photo_votes_count": photo_votes_count,
            "level": level,
            "role": row["role"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в get_user_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

# ===== СТАРТОВАЯ СТРАНИЦА (МТБ Парки) =====

DEFAULT_START_PARKS = [p["id"] for p in PARKS["mtb_parks"]["parks"][:4]]


class StartParksUpdate(BaseModel):
    park_ids: List[str] = Field(default_factory=list, max_length=50)


@router.get("/api/user/start-parks")
async def get_start_parks(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT start_page_configured FROM users WHERE id = ?", (user["user_id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        configured = bool(row["start_page_configured"])
        if not configured:
            return {"configured": False, "parks": [{"park_id": pid} for pid in DEFAULT_START_PARKS]}
        rows = conn.execute(
            "SELECT park_id FROM start_page_parks WHERE user_id = ? ORDER BY sort_order",
            (user["user_id"],)
        ).fetchall()
        return {"configured": True, "parks": [{"park_id": r["park_id"]} for r in rows]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в get_start_parks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


@router.post("/api/user/start-parks")
async def set_start_parks(data: StartParksUpdate, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        for pid in data.park_ids:
            park = conn.execute("SELECT id FROM parks WHERE id = ?", (pid,)).fetchone()
            if not park:
                raise HTTPException(status_code=404, detail=f"Парк не найден: {pid}")
        existing = set(
            r["park_id"]
            for r in conn.execute(
                "SELECT park_id FROM start_page_parks WHERE user_id = ?", (user["user_id"],)
            ).fetchall()
        )
        added = any(pid not in existing for pid in data.park_ids)
        conn.execute("DELETE FROM start_page_parks WHERE user_id = ?", (user["user_id"],))
        for idx, pid in enumerate(data.park_ids):
            conn.execute(
                "INSERT INTO start_page_parks (user_id, park_id, sort_order) VALUES (?, ?, ?)",
                (user["user_id"], pid, idx)
            )
        conn.execute("UPDATE users SET start_page_configured = 1 WHERE id = ?", (user["user_id"],))
        conn.commit()
        return {"ok": True, "added": added}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в set_start_parks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


@router.delete("/api/user/start-parks")
async def clear_start_parks(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM start_page_parks WHERE user_id = ?", (user["user_id"],))
        conn.execute("UPDATE users SET start_page_configured = 0 WHERE id = ?", (user["user_id"],))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в clear_start_parks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


# ===== БАЙКИ (ГАРАЖ) =====

class BikeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    rider_weight_kg: Optional[float] = 75
    tire_type: str = "mtb"

class BikeUpdate(BaseModel):
    name: str = None
    rider_weight_kg: Optional[float] = None
    tire_type: str = None

@router.get("/api/user/bikes")
async def get_bikes(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, photo, rider_weight_kg, tire_type FROM bikes WHERE user_id = ? ORDER BY created_at DESC",
            (user["user_id"],)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Ошибка в get_bikes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@router.post("/api/user/bikes")
async def create_bike(bike: BikeCreate, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO bikes (user_id, name, rider_weight_kg, tire_type) VALUES (?, ?, ?, ?)",
            (user["user_id"], bike.name, bike.rider_weight_kg, bike.tire_type)
        )
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}
    except Exception as e:
        logger.error(f"Ошибка в create_bike: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@router.put("/api/user/bikes/{bike_id}")
async def update_bike(bike_id: int, bike: BikeUpdate, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM bikes WHERE id = ? AND user_id = ?",
            (bike_id, user["user_id"])
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Байк не найден")
        updates = {}
        if bike.name is not None: updates["name"] = bike.name
        if bike.rider_weight_kg is not None: updates["rider_weight_kg"] = bike.rider_weight_kg
        if bike.tire_type is not None: updates["tire_type"] = bike.tire_type
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [bike_id, user["user_id"]]
            conn.execute(f"UPDATE bikes SET {set_clause} WHERE id = ? AND user_id = ?", vals)
            conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в update_bike: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@router.delete("/api/user/bikes/{bike_id}")
async def delete_bike(bike_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM bikes WHERE id = ? AND user_id = ?",
            (bike_id, user["user_id"])
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в delete_bike: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@router.get("/api/user/profile")
async def get_profile(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        u = conn.execute(
            "SELECT id, email, username, avatar, role FROM users WHERE id = ?",
            (user["user_id"],)
        ).fetchone()
        if not u:
            raise HTTPException(status_code=404)
        bikes = conn.execute(
            "SELECT id, name, photo, rider_weight_kg, tire_type FROM bikes WHERE user_id = ? ORDER BY created_at DESC",
            (user["user_id"],)
        ).fetchall()
        return {
            "id": u["id"],
            "email": u["email"],
            "username": u["username"],
            "avatar": u["avatar"],
            "role": u["role"],
            "bikes": [dict(b) for b in bikes]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в get_profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@router.post("/api/user/avatar")
async def upload_avatar(request: Request, user=Depends(get_current_user)):
    import uuid
    from api.upload_utils import parse_file, check_upload_limit, body_too_large

    if body_too_large(request):
        return JSONResponse({"error": "Файл слишком большой (максимум 15 МБ)"}, status_code=413)

    body = await request.json()
    file_data = body.get("file", "")
    file_bytes, ext, error = parse_file(file_data)
    if error:
        status = 413 if "слишком большой" in error else 400
        return JSONResponse({"error": error}, status_code=status)
    if not check_upload_limit(user["user_id"]):
        return JSONResponse({"error": "Лимит: не более 10 загрузок в час"}, status_code=429)
    filename = f"avatar_{user['user_id']}_{uuid.uuid4().hex[:6]}.{ext}"
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, "data", "photos", "avatars", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"Ошибка записи аватара {filename}: {e}")
        return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET avatar = ? WHERE id = ?", (f"/photos/avatars/{filename}", user["user_id"]))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения аватара {filename} в БД: {e}")
        try:
            os.remove(filepath)
        except OSError:
            pass
        return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
    finally:
        conn.close()
    return {"ok": True, "url": f"/photos/avatars/{filename}"}

@router.post("/api/user/bikes/{bike_id}/photo")
async def upload_bike_photo(bike_id: int, request: Request, user=Depends(get_current_user)):
    import uuid
    from api.upload_utils import parse_file, check_upload_limit, body_too_large

    conn = get_connection()
    try:
        bike = conn.execute("SELECT id FROM bikes WHERE id = ? AND user_id = ?", (bike_id, user["user_id"])).fetchone()
        if not bike:
            raise HTTPException(status_code=404, detail="Байк не найден")
        if body_too_large(request):
            return JSONResponse({"error": "Файл слишком большой (максимум 15 МБ)"}, status_code=413)
        body = await request.json()
        file_data = body.get("file", "")
        file_bytes, ext, error = parse_file(file_data)
        if error:
            status = 413 if "слишком большой" in error else 400
            return JSONResponse({"error": error}, status_code=status)
        if not check_upload_limit(user["user_id"]):
            return JSONResponse({"error": "Лимит: не более 10 загрузок в час"}, status_code=429)
        filename = f"bike_{bike_id}_{uuid.uuid4().hex[:6]}.{ext}"
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "data", "photos", "bikes", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        try:
            with open(filepath, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            logger.error(f"Ошибка записи фото байка {filename}: {e}")
            return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
        try:
            conn.execute("UPDATE bikes SET photo = ? WHERE id = ?", (f"/photos/bikes/{filename}", bike_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения фото байка {filename} в БД: {e}")
            try:
                os.remove(filepath)
            except OSError:
                pass
            return JSONResponse({"error": "Внутренняя ошибка"}, status_code=500)
        return {"ok": True, "url": f"/photos/bikes/{filename}"}
    finally:
        conn.close()

@router.get("/api/user/dashboard-parks")
async def get_dashboard_parks(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT park_id FROM user_dashboard_parks WHERE user_id = ? ORDER BY sort_order",
            (user["user_id"],)
        ).fetchall()
        return [{"park_id": r["park_id"]} for r in rows]
    except Exception as e:
        logger.error(f"Ошибка в get_dashboard_parks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


@router.post("/api/user/dashboard-parks/{park_id}")
async def add_to_dashboard(park_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        park = conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM user_dashboard_parks WHERE user_id = ?",
            (user["user_id"],)
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO user_dashboard_parks (user_id, park_id, sort_order) VALUES (?, ?, ?)",
            (user["user_id"], park_id, max_order + 1)
        )
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в add_to_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


@router.delete("/api/user/dashboard-parks/{park_id}")
async def remove_from_dashboard(park_id: str, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM user_dashboard_parks WHERE user_id = ? AND park_id = ?",
            (user["user_id"], park_id)
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в remove_from_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()


@router.delete("/api/user/dashboard-parks")
async def clear_dashboard(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM user_dashboard_parks WHERE user_id = ?", (user["user_id"],))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в clear_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()