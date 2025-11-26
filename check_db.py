import sqlite3

conn = sqlite3.connect("db/agent.db")
cursor = conn.cursor()

# Check schema
cursor.execute("PRAGMA table_info(actions)")
cols = cursor.fetchall()
print("Columns:", [c[1] for c in cols])

# Check total
cursor.execute("SELECT COUNT(*) FROM actions")
print(f"\nTotal records: {cursor.fetchone()[0]}")

# Check records with data
cursor.execute(
    """
    SELECT author, message, avatar_url, reply_text, detail
    FROM actions 
    WHERE author IS NOT NULL AND LENGTH(author) > 0
    LIMIT 5
"""
)
rows = cursor.fetchall()
print(f"\nRecords with author: {len(rows)}")
for r in rows:
    print(f"  Author: [{r[0]}]")
    print(f'  Message: [{r[1][:80] if r[1] else "NULL"}]')
    print(f'  Avatar: [{r[2][:60] if r[2] else "NULL"}]')
    print(f'  Reply: [{r[3][:60] if r[3] else "NULL"}]')
    print(f"  Detail: [{r[4]}]")
    print()

# Check all records
cursor.execute("SELECT author, message, avatar_url FROM actions LIMIT 10")
all_rows = cursor.fetchall()
print(f"\nFirst 10 records (any):")
for i, r in enumerate(all_rows):
    print(
        f'  {i+1}. Author=[{r[0]}], Msg=[{r[1][:40] if r[1] else "NULL"}], Avatar=[{r[2][:40] if r[2] else "NULL"}]'
    )

conn.close()
