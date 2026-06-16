import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")


def get_connection():
    """Создаёт подключение к SQLite с WAL-режимом"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Создаёт все таблицы, если их нет, и добавляет недостающие колонки"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS parks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            group_id TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            soil_type TEXT DEFAULT 'loam',
            forest_coef REAL DEFAULT 0.3,
            start_date TEXT,
            is_active INTEGER DEFAULT 1,
            current_moisture REAL DEFAULT 0.0,
            last_updated DATETIME
        );

        CREATE TABLE IF NOT EXISTS weather_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            temperature REAL,
            rain REAL DEFAULT 0.0,
            wind_speed REAL,
            radiation REAL,
            source TEXT DEFAULT 'openmeteo',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (park_id) REFERENCES parks(id),
            UNIQUE(park_id, timestamp)
        );

        CREATE INDEX IF NOT EXISTS idx_weather_park_time
        ON weather_hourly(park_id, timestamp DESC);

        CREATE INDEX IF NOT EXISTS idx_weather_source
        ON weather_hourly(source);

        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            update_type TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS park_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            user_id INTEGER,
            filename TEXT NOT NULL,
            original_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Добавляем новые колонки, если их ещё нет
    try:
        cursor.execute("ALTER TABLE weather_hourly ADD COLUMN relative_humidity REAL")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE weather_hourly ADD COLUMN surface_pressure REAL")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


def get_db():
    """Генератор подключений (для FastAPI Depends)"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()