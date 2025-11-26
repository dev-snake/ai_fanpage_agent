"""
Test Database class trực tiếp
"""

from db.database import Database
from datetime import datetime

print("Creating Database instance...")
db = Database("db/test_db_class.db")

print("\nInserting record...")
db.record_action(
    comment_id="test_123",
    post_id="post_456",
    author="Test User",
    avatar_url="http://example.com/avatar.jpg",
    message="Test message content",
    intent="test_intent",
    actions=["reply", "hide"],
    detail="test detail",
    reply_text="Test reply text from AI",
    timestamp=datetime.utcnow(),
)

print("✅ record_action() completed")

# Read back using Database method
print("\nReading with Database.actions()...")
records = db.actions(limit=1)
if records:
    r = records[0]
    print(f"  Author: [{r.get('author')}]")
    print(f"  Message: [{r.get('message')}]")
    print(f"  Avatar: [{r.get('avatar_url')}]")
    print(f"  Reply: [{r.get('reply_text')}]")
else:
    print("  No records!")

# Read back using direct SQL
print("\nReading with direct SQL...")
import sqlite3

conn = sqlite3.connect("db/test_db_class.db")
cursor = conn.cursor()
cursor.execute("SELECT author, message, avatar_url, reply_text FROM actions")
row = cursor.fetchone()
print(f"  Author: [{row[0]}]")
print(f"  Message: [{row[1]}]")
print(f"  Avatar: [{row[2]}]")
print(f"  Reply: [{row[3]}]")
conn.close()

db.close()

if records and records[0].get("author"):
    print("\n🎉 SUCCESS!")
else:
    print("\n❌ FAILED - Database class has a bug!")
