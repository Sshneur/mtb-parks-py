import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")


def get_connection():
    """Создаёт подключение к SQLite с WAL-режимом"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
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
            vote INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weather_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            date TEXT NOT NULL,
            temperature_max REAL,
            rain_sum REAL,
            weather_code INTEGER,
            UNIQUE(park_id, date)
        );

        CREATE TABLE IF NOT EXISTS votes_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            user_id INTEGER,
            vote INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dry_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id TEXT NOT NULL,
            date TEXT NOT NULL,
            dry_hours REAL,
            UNIQUE(park_id, date)
        );

        CREATE TABLE IF NOT EXISTS soil_forecast_cache (
            park_id TEXT PRIMARY KEY,
            forecast_data TEXT NOT NULL,
            fetched_at DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bikes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            photo TEXT,
            rider_weight_kg REAL DEFAULT 75,
            tire_type TEXT DEFAULT 'mtb',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    # Добавляем новые колонки, если их ещё нет
    def _add_column(sql):
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass
        except Exception as e:
            logger.warning(f"Миграция колонки пропущена: {e}")

    _add_column("ALTER TABLE weather_hourly ADD COLUMN relative_humidity REAL")
    _add_column("ALTER TABLE weather_hourly ADD COLUMN surface_pressure REAL")
    _add_column("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
    _add_column("ALTER TABLE users ADD COLUMN locked_until TEXT")
    _add_column("ALTER TABLE users ADD COLUMN username TEXT")
    _add_column("ALTER TABLE park_photos ADD COLUMN vote INTEGER")
    _add_column("ALTER TABLE users ADD COLUMN photo_votes_count INTEGER DEFAULT 0")
    _add_column("ALTER TABLE weather_daily ADD COLUMN weather_code INTEGER")
    _add_column("ALTER TABLE park_photos ADD COLUMN comment TEXT DEFAULT ''")
    _add_column("ALTER TABLE parks ADD COLUMN description TEXT DEFAULT ''")
    _add_column("ALTER TABLE parks ADD COLUMN trails_count INTEGER DEFAULT 0")
    _add_column("ALTER TABLE parks ADD COLUMN dry_hours_default INTEGER DEFAULT 72")
    _add_column("ALTER TABLE parks ADD COLUMN evaporation_rate REAL DEFAULT 0.001")
    _add_column("ALTER TABLE users ADD COLUMN avatar TEXT")

    # Обновляем description и trails_count для существующих парков
    from database.models import PARKS as PARKS_DATA
    for group_id, group_data in PARKS_DATA.items():
        for park in group_data["parks"]:
            cursor.execute(
                "UPDATE parks SET description = ?, trails_count = ? WHERE id = ? AND (description IS NULL OR description = '')",
                (park.get("description", ""), park.get("trails_count", 0), park["id"])
            )

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


def get_db():
    """Генератор подключений для FastAPI Depends"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()