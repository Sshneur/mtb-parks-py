from database.connection import get_connection
conn = get_connection()
conn.execute("UPDATE parks SET forest_coef=0.225 WHERE id='chess'")
conn.commit()
conn.close()
print("✅ forest_coef для Чесс Парка изменён на 0.225")