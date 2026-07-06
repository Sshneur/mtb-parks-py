from database.connection import get_connection

conn = get_connection()
# Удаляем запись с неверной датой
conn.execute("DELETE FROM dry_dates WHERE park_id = 'chess' AND dry_date = '2026-05-02'")
# Вставляем правильную дату
conn.execute("INSERT OR IGNORE INTO dry_dates (park_id, dry_date) VALUES ('chess', '2026-05-21')")
conn.commit()
conn.close()
print("✅ Дата для Чесс Парка исправлена на 2026-05-21")