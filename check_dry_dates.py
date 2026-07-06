from database.connection import get_connection

conn = get_connection()
rows = conn.execute("SELECT park_id, dry_date, created_at FROM dry_dates ORDER BY created_at DESC LIMIT 10").fetchall()
if rows:
    for r in rows:
        print(f"{r['park_id']} -> {r['dry_date']} (записано {r['created_at']})")
else:
    print("Таблица dry_dates пуста – ни одна дата ещё не сохранена.")
conn.close()