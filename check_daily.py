from database.connection import get_connection
conn = get_connection()
cnt = conn.execute("SELECT COUNT(*) FROM weather_daily WHERE park_id='fili'").fetchone()[0]
print(f'Записей в weather_daily для Фили: {cnt}')
if cnt > 0:
    min_date = conn.execute("SELECT MIN(date) FROM weather_daily WHERE park_id='fili'").fetchone()[0]
    max_date = conn.execute("SELECT MAX(date) FROM weather_daily WHERE park_id='fili'").fetchone()[0]
    print(f'С {min_date} по {max_date}')
else:
    print('Таблица пуста')
conn.close()