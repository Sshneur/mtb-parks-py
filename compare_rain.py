from database.connection import get_connection
from datetime import datetime, timezone, timedelta

conn = get_connection()
now_utc = datetime.now(timezone.utc)

# 1. Сумма из почасовой таблицы за последние 7 дней (168 часов)
since_hourly = (now_utc - timedelta(days=7)).isoformat()
rain_hourly = conn.execute(
    "SELECT SUM(rain) FROM weather_hourly WHERE park_id='fili' AND timestamp >= ?",
    (since_hourly,)
).fetchone()[0]
print(f"1. Сумма осадков за последние 7 дней (почасовая, главная страница): {rain_hourly:.1f} мм")

# 2. Сумма из дневной таблицы за последние 7 календарных дней
since_daily = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
rows = conn.execute(
    "SELECT date, rain_sum FROM weather_daily WHERE park_id='fili' AND date >= ? ORDER BY date ASC",
    (since_daily,)
).fetchall()
total_daily = 0.0
print("\n2. Дни в weather_daily (графики):")
for r in rows:
    print(f"   {r['date']}: {r['rain_sum']:.1f} мм")
    total_daily += r['rain_sum'] or 0.0
print(f"   Сумма за 7 дней (daily): {total_daily:.1f} мм")

# 3. Сумма из weather_daily за тот же период, что и hourly (7 полных суток)
since_daily2 = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
rows2 = conn.execute(
    "SELECT date, rain_sum FROM weather_daily WHERE park_id='fili' AND date >= ? ORDER BY date ASC",
    (since_daily2,)
).fetchall()
total_daily2 = 0.0
print("\n3. Дни в weather_daily за тот же период, что и hourly:")
for r in rows2:
    print(f"   {r['date']}: {r['rain_sum']:.1f} мм")
    total_daily2 += r['rain_sum'] or 0.0
print(f"   Сумма (daily, тот же период): {total_daily2:.1f} мм")

conn.close()
