import sqlite3

conn = sqlite3.connect('hamburg_jobs.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM jobs")
rows = cursor.fetchall()

print(f"Total jobs in memory: {len(rows)}")
for row in rows:
    print(f"ID: {row[0]} | Title: {row[1]}")

conn.close()