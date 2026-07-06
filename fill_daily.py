from database.connection import get_connection
conn = get_connection()
# Очищаем таблицу (перезапишем)
conn.execute("DELETE FROM weather_daily")
conn.commit()
# Заполняем из weather_hourly за последние 30 дней
for park in conn.execute("SELECT id FROM parks").fetchall():
    pid = park["id"]
    rows = conn.execute("""
        SELECT DATE(timestamp) as day,
               MAX(temperature) as tmax,
               SUM(rain) as rain_sum
        FROM weather_hourly
        WHERE park_id = ? AND timestamp >= date('now', '-30 days')
        GROUP BY day
        ORDER BY day
    """, (pid,)).fetchall()
    for r in rows:
        conn.execute("""
            INSERT OR REPLACE INTO weather_daily
            (park_id, date, temperature_max, rain_sum)
            VALUES (?, ?, ?, ?)
        """, (pid, r["day"], r["tmax"], r["rain_sum"] or 0))
conn.commit()
conn.close()
print("Все данные за 30 дней перенесены в weather_daily")