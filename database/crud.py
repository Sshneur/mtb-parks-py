import sqlite3
from datetime import datetime, timedelta
from .connection import get_connection
from .models import PARKS


def seed_parks():
    """Переносит парки из PARKS в БД (если их там нет)"""
    conn = get_connection()
    cursor = conn.cursor()

    for group_id, group_data in PARKS.items():
        for park in group_data["parks"]:
            cursor.execute("""
                INSERT OR IGNORE INTO parks 
                (id, name, group_id, lat, lon, soil_type, forest_coef)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                park["id"],
                park["name"],
                group_id,
                park["lat"],
                park["lon"],
                park.get("soil", "loam"),
                park.get("forest_coef", 0.3)
            ))

    conn.commit()
    conn.close()
    print("✅ Парки перенесены в БД")


def get_all_parks():
    """Все активные парки"""
    conn = get_connection()
    parks = conn.execute("SELECT * FROM parks WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(p) for p in parks]


def get_parks_by_group(group_id: str):
    """Парки одной группы"""
    conn = get_connection()
    parks = conn.execute(
        "SELECT * FROM parks WHERE group_id = ? AND is_active = 1", 
        (group_id,)
    ).fetchall()
    conn.close()
    return [dict(p) for p in parks]


def get_park(park_id: str):
    """Один парк по ID"""
    conn = get_connection()
    park = conn.execute("SELECT * FROM parks WHERE id = ?", (park_id,)).fetchone()
    conn.close()
    return dict(park) if park else None


def update_park_moisture(park_id: str, moisture: float):
    """Обновляет current_moisture и last_updated"""
    conn = get_connection()
    conn.execute("""
        UPDATE parks 
        SET current_moisture = ?, last_updated = ?
        WHERE id = ?
    """, (moisture, datetime.utcnow().isoformat(), park_id))
    conn.commit()
    conn.close()


def insert_weather_hourly(park_id: str, timestamp, temperature, rain, wind_speed, radiation, source: str):
    """Вставляет почасовые данные. Заменяет существующую запись, если timestamp совпадает."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO weather_hourly 
            (park_id, timestamp, temperature, rain, wind_speed, radiation, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (park_id, timestamp, temperature, rain, wind_speed, radiation, source))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка вставки: {e}")
        return False
    finally:
        conn.close()


def get_weather_hourly(park_id: str, hours: int = 24):
    """Почасовые данные за последние N часов"""
    conn = get_connection()
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = conn.execute("""
        SELECT * FROM weather_hourly 
        WHERE park_id = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (park_id, since)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_weather_records(park_id: str) -> int:
    """Сколько записей погоды есть для парка"""
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM weather_hourly WHERE park_id = ?", 
        (park_id,)
    ).fetchone()[0]
    conn.close()
    return count


def log_update(park_id: str, update_type: str, status: str, message: str = ""):
    """Записывает в лог обновлений"""
    conn = get_connection()
    conn.execute("""
        INSERT INTO update_log (park_id, update_type, status, message)
        VALUES (?, ?, ?, ?)
    """, (park_id, update_type, status, message))
    conn.commit()
    conn.close()