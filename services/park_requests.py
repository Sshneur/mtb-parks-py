"""Сервис модерации заявок «Предложи свой парк».

Быстрый (Telegram) и полный (админка) режимы одобрения.
"""
import sqlite3

from database.connection import get_connection
from database.models import SOIL_COEFFICIENTS

# Транслитерация для генерации park_id из названия
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def translit_id(name: str) -> str:
    """Транслит названия в URL-безопасный id (park, park-2, ...)."""
    out = []
    for ch in (name or "").lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum() or ch in " -_":
            out.append(ch)
    slug = "".join(out).strip().replace(" ", "-").replace("_", "-")
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "park"


def guess_soil_type(text: str) -> str:
    """Определяет тип грунта по свободному описанию (быстрый режим Telegram)."""
    low = (text or "").lower()
    if any(k in low for k in ("асфальт", "асфальтовый", "асфальтированный")):
        return "asphalt"
    if any(k in low for k in ("подзол", "подзолист", "дерново-подзолист")):
        return "podzol"
    if any(k in low for k in ("чернозём", "чернозем")):
        return "chernozem"
    if any(k in low for k in ("глина", "глинист", "глинян")):
        return "clay"
    if any(k in low for k in ("супесь", "супес", "песок", "песчан", "песчаный")):
        return "sand"
    if any(k in low for k in ("суглин", "суглинок", "суглинист")):
        return "loam"
    return "loam"


def approve_park_request(
    request_id: int,
    *,
    group_id: str = "mtb_parks",
    forest_coef: float = 0.3,
    dry_hours_default: int = 48,
    soil_type: str = None,
) -> dict:
    """Создаёт парк из заявки и помечает её одобренной. Возвращает park_id."""
    conn = get_connection()
    try:
        req = conn.execute("SELECT * FROM park_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            raise ValueError("Заявка не найдена")
        if req["status"] != "pending":
            raise ValueError(f"Заявка уже обработана ({req['status']})")

        soil = soil_type or guess_soil_type(req["soil_description"])
        if soil not in SOIL_COEFFICIENTS:
            soil = "loam"

        base = translit_id(req["name"])
        park_id = base
        suffix = 2
        while conn.execute("SELECT id FROM parks WHERE id = ?", (park_id,)).fetchone():
            park_id = f"{base}_{suffix}"
            suffix += 1

        conn.execute("""
            INSERT INTO parks
            (id, name, group_id, lat, lon, soil_type, forest_coef,
             description, trails_count, dry_hours_default, storm_drain, tg_group, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            park_id,
            req["name"],
            group_id,
            req["lat"],
            req["lon"],
            soil,
            forest_coef,
            req["description"],
            req["trails_count"],
            dry_hours_default,
            req["storm_drain"],
            req["tg_group"],
        ))
        conn.execute("UPDATE park_requests SET status = 'approved' WHERE id = ?", (request_id,))
        conn.commit()
        return {"park_id": park_id, "request_id": request_id}
    finally:
        conn.close()


def reject_park_request(request_id: int) -> bool:
    """Помечает заявку отклонённой. Возвращает True, если заявка была найдена."""
    conn = get_connection()
    try:
        req = conn.execute("SELECT id, status FROM park_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return False
        if req["status"] != "pending":
            raise ValueError(f"Заявка уже обработана ({req['status']})")
        conn.execute("UPDATE park_requests SET status = 'rejected' WHERE id = ?", (request_id,))
        conn.commit()
        return True
    finally:
        conn.close()