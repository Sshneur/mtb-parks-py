from database.connection import get_connection

conn = get_connection()
conn.execute("UPDATE parks SET forest_coef=0.20 WHERE id='erino'")
conn.commit()
conn.close()
print("✅ forest_coef для Ерино обновлён на 0.20")