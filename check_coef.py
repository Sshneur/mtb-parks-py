from database.connection import get_connection

conn = get_connection()
for pid in ['chess', 'erino']:
    row = conn.execute("SELECT id, forest_coef FROM parks WHERE id=?", (pid,)).fetchone()
    if row:
        print(f"{row['id']}: forest_coef = {row['forest_coef']}")
conn.close()