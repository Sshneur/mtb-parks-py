from database.connection import get_connection
conn = get_connection()
rows = conn.execute("SELECT id, park_id, filename, status, created_at FROM park_photos ORDER BY created_at DESC LIMIT 5").fetchall()
if rows:
    for r in rows:
        print(f'{r["id"]} | {r["park_id"]} | {r["filename"]} | status={r["status"]} | {r["created_at"]}')
else:
    print("Таблица park_photos пуста")
conn.close()