import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_parks (
            user_id INTEGER,
            park_id TEXT,
            PRIMARY KEY (user_id, park_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (park_id) REFERENCES parks(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            endpoint TEXT,
            ip TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS soil_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            park_id TEXT NOT NULL,
            vote INTEGER NOT NULL CHECK(vote BETWEEN 1 AND 5),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, park_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Миграция выполнена: добавлены таблицы users, favorite_parks, request_log, soil_votes")

if __name__ == "__main__":
    migrate()