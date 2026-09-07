from database.connection import get_connection


def migrate():
    conn = get_connection()
    try:
        # 1. Гарантируем, что целевая таблица существует (идемпотентно)
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

        # 2. Проверяем, существует ли таблица-источник
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='favorite_parks'"
        ).fetchone()

        if row:
            # 3. Переносим: парки, которых ещё нет в панели, с сортировкой по user_id
            #    INSERT OR IGNORE исключает дубли (уникальный PK user_id+park_id)
            conn.execute("""
                INSERT OR IGNORE INTO user_dashboard_parks (user_id, park_id, sort_order)
                SELECT user_id, park_id,
                       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY rowid) AS sort_order
                FROM favorite_parks
            """)

            # 4. Не трогаем те парки, что уже были в панели — INSERT OR IGNORE их пропустит.
            #    Для существующих записей в панели sort_order не меняется.

            total = conn.execute(
                "SELECT COUNT(*) AS c FROM user_dashboard_parks"
            ).fetchone()["c"]
            print(f"✅ Перенесены избранные в 'Мои парки'. Всего записей: {total}")

            # 5. Только после успешного переноса удаляем старую таблицу
            conn.execute("DROP TABLE IF EXISTS favorite_parks")
            conn.commit()
            print("✅ Таблица favorite_parks удалена (функционал 'Избранное' убран)")
        else:
            print("⏭️ favorite_parks уже нет — перенос пропущен")
    except Exception as e:
        print(f"⚠️ Миграция remove_favorites: {e}")
    finally:
        conn.close()
