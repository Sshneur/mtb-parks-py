from database.connection import get_connection
conn = get_connection()
rows = conn.execute('''
    SELECT timestamp, rain, temperature, wind_speed, radiation, relative_humidity, surface_pressure
    FROM weather_hourly
    WHERE park_id='arkhyz' AND rain > 0
    ORDER BY timestamp DESC
    LIMIT 20
''').fetchall()
for r in rows:
    print(f'{r["timestamp"]} rain={r["rain"]:.1f}mm temp={r["temperature"]}°C wind={r["wind_speed"]}m/s rad={r["radiation"]}W/m² hum={r["relative_humidity"]}% press={r["surface_pressure"]}hPa')
conn.close()
