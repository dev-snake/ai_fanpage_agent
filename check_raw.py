import sqlite3

conn = sqlite3.connect("db/test_db_class.db")
cursor = conn.cursor()

# Check schema
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="actions"')
print("Table schema:")
print(cursor.fetchone()[0])

# Check raw data
cursor.execute("SELECT id, created_at, author, message FROM actions")
rows = cursor.fetchall()
print(f"\nTotal rows: {len(rows)}")
for row in rows:
    print(f"  ID={row[0]}, created_at={row[1]}, author='{row[2]}', message='{row[3]}'")

conn.close()
