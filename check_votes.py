from database.connection import get_connection

conn = get_connection()
rows = conn.execute("SELECT user_id, vote FROM soil_votes WHERE park_id='fili'").fetchall()
for r in rows:
    print(f"user {r['user_id']}: {r['vote']}")
row = conn.execute("SELECT AVG(vote) FROM soil_votes WHERE park_id='fili'").fetchone()
print(f"Среднее: {row[0]}")
conn.close()