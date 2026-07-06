import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Добавляем колонку vote в park_photos
    try:
        cursor.execute("ALTER TABLE park_photos ADD COLUMN vote INTEGER")
        print("✅ Колонка vote добавлена в park_photos")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ Колонка vote уже существует")
        else:
            print(f"⚠️ Ошибка: {e}")

    # Добавляем колонку photo_votes_count в users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN photo_votes_count INTEGER DEFAULT 0")
        print("✅ Колонка photo_votes_count добавлена в users")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ Колонка photo_votes_count уже существует")
        else:
            print(f"⚠️ Ошибка: {e}")

    conn.commit()
    conn.close()
    print("✅ Миграция завершена")

if __name__ == "__main__":
    migrate()