import sqlite3

from database.connection import get_connection


def migrate():
    """Стартовая страница «МТБ Парки» + предложенные парки (модерация)."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS start_page_parks (
                user_id INTEGER,
                park_id TEXT,
                sort_order INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, park_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (park_id) REFERENCES parks(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS park_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                soil_description TEXT DEFAULT '',
                storm_drain TEXT DEFAULT '',
                contact_tg TEXT DEFAULT '',
                tg_group TEXT DEFAULT '',
                trails_count INTEGER DEFAULT 0,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("ALTER TABLE parks ADD COLUMN storm_drain TEXT DEFAULT ''")
        conn.execute("ALTER TABLE parks ADD COLUMN tg_group TEXT DEFAULT ''")
        conn.execute("ALTER TABLE users ADD COLUMN start_page_configured INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Миграция add_park_requests: таблицы start_page_parks и park_requests созданы, колонки добавлены")
    except sqlite3.OperationalError:
        print("⚠️ Миграция add_park_requests: колонки/таблицы уже существуют")
    except Exception as e:
        print(f"⚠️ Миграция add_park_requests: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()