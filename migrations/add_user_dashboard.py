import sqlite3
from database.connection import get_connection

def migrate():
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_dashboard_parks (
                user_id INTEGER,
                park_id TEXT,
                sort_order INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, park_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (park_id) REFERENCES parks(id)
            )
        """)
        conn.commit()
        print("✅ Таблица user_dashboard_parks создана")
    except Exception as e:
        print(f"⚠️ Миграция user_dashboard_parks: {e}")
    finally:
        conn.close()