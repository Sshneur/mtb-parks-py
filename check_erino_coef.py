from database.connection import get_connection
conn = get_connection()
row = conn.execute("SELECT forest_coef FROM parks WHERE id='erino'").fetchone()
if row:
    print(f"Текущий forest_coef для Ерино: {row['forest_coef']}")
else:
    print("Парк не найден")
conn.close()