import sqlite3
from database.connection import get_connection

def migrate():
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN oauth_provider TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN oauth_id TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN oauth_token TEXT")
        conn.commit()
        print("✅ OAuth колонки добавлены в таблицу users")
    except sqlite3.OperationalError:
        print("⚠️ OAuth колонки уже существуют")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
