"""
Direct SQL test để tìm bug
"""

import sqlite3
from datetime import datetime
import json

# Tạo database mới
conn = sqlite3.connect("db/test_direct.db")
cursor = conn.cursor()

# Tạo table giống hệt
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        comment_id TEXT,
        post_id TEXT,
        author TEXT,
        avatar_url TEXT,
        message TEXT,
        intent TEXT,
        actions TEXT,
        detail TEXT,
        reply_text TEXT
    )
"""
)
conn.commit()

print("Table created")

# Test INSERT trực tiếp
test_values = (
    datetime.utcnow().isoformat(),  # created_at
    "test_comment_123",  # comment_id
    "post_456",  # post_id
    "Unknown",  # author - ĐÂY LÀ VẤN ĐỀ?
    None,  # avatar_url
    "giá",  # message
    "ask_price",  # intent
    json.dumps(["reply"]),  # actions
    "test detail",  # detail
    "test reply text",  # reply_text
)

print(f"\nINSERT values:")
for i, val in enumerate(test_values):
    print(f"  {i}: [{val}]")

cursor.execute(
    """
    INSERT INTO actions (
        created_at, comment_id, post_id, author, avatar_url,
        message, intent, actions, detail, reply_text
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
    test_values,
)
conn.commit()

print("\n✅ INSERT done")

# SELECT back
cursor.execute("SELECT author, message, avatar_url, reply_text FROM actions")
row = cursor.fetchone()

print(f"\nSELECT results:")
print(f"  Author: [{row[0]}]")
print(f"  Message: [{row[1]}]")
print(f"  Avatar: [{row[2]}]")
print(f"  Reply: [{row[3]}]")

if row[0] and row[1]:
    print("\n🎉 SUCCESS - Data saved correctly!")
else:
    print("\n❌ FAILED - Data is NULL!")

conn.close()
