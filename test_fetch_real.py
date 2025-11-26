"""
Test script để fetch comments thật từ Facebook và kiểm tra data
"""

import sys
import logging
from pathlib import Path
import json
import os


# Load env manually
def load_env():
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


load_env()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test")

# Load config
config_path = Path("config.json")
config_data = json.loads(config_path.read_text(encoding="utf-8"))

# Replace ${VAR} với env vars
for key, value in config_data.items():
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        config_data[key] = os.getenv(env_var, value)

# Force demo = False
config_data["demo"] = False

logger.info(
    f"Config loaded: demo={config_data.get('demo')}, page_id={config_data.get('page_id')}"
)

# Test fetch
from core.comments import CommentFetcher
from core.token_manager import TokenManager

token_manager = TokenManager(
    config_path=config_path, logger=logger, config_dict=config_data
)

fetcher = CommentFetcher(cfg=config_data, logger=logger, token_manager=token_manager)

logger.info(f"Fetcher demo mode: {fetcher.demo}")
logger.info("Fetching real comments from Facebook...")

try:
    comments = fetcher.fetch_new(limit=5)
    logger.info(f"✅ Fetched {len(comments)} comments")

    for i, c in enumerate(comments):
        logger.info(f"\n{'='*60}")
        logger.info(f"Comment #{i+1}")
        logger.info(f"  ID: {c.id}")
        logger.info(f"  Author: {c.author}")
        logger.info(f"  Avatar: {c.avatar_url}")
        logger.info(f"  Message: {c.message[:100] if c.message else '(empty)'}")
        logger.info(f"  Created: {c.created_at}")
        logger.info(f"  Permalink: {c.permalink}")

        # Debug: Check raw data
        if c.raw:
            logger.info(f"  Raw 'from' field: {c.raw.get('from')}")
            logger.info(f"  Raw keys: {list(c.raw.keys())}")

    # Test save to DB
    from db.database import Database
    from core.ai_engine import classify_comment

    db = Database("db/agent_test.db")

    if comments:
        first_comment = comments[0]
        decision = classify_comment(first_comment, config_data, logger)

        logger.info(f"\n{'='*60}")
        logger.info("Testing database save...")
        logger.info(f"  Comment ID: {first_comment.id}")
        logger.info(f"  Comment author: [{first_comment.author}]")
        logger.info(f"  Comment message: [{first_comment.message}]")
        logger.info(f"  Comment avatar: [{first_comment.avatar_url}]")
        logger.info(f"  Intent: {decision.intent}")
        logger.info(f"  Reply text: {decision.reply_text}")

        db.record_action(
            comment_id=first_comment.id,
            post_id=first_comment.post_id,
            author=first_comment.author,
            avatar_url=first_comment.avatar_url,
            message=first_comment.message,
            intent=decision.intent.value,
            actions=[a.value for a in decision.actions],
            detail="test save",
            reply_text=decision.reply_text or "",
        )

        logger.info("\n📝 SQL INSERT values:")
        logger.info(f"  author param: [{first_comment.author}]")
        logger.info(f"  message param: [{first_comment.message}]")
        logger.info(f"  avatar_url param: [{first_comment.avatar_url}]")

        # Verify
        import sqlite3

        conn = sqlite3.connect("db/agent_test.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT author, message, avatar_url, reply_text FROM actions LIMIT 1"
        )
        row = cursor.fetchone()
        logger.info(f"\n✅ Database verification:")
        logger.info(f"  Author saved: [{row[0]}]")
        logger.info(f"  Message saved: [{row[1][:50] if row[1] else 'NULL'}]")
        logger.info(f"  Avatar saved: [{row[2][:50] if row[2] else 'NULL'}]")
        logger.info(f"  Reply saved: [{row[3][:50] if row[3] else 'NULL'}]")
        conn.close()

        logger.info(f"\n🎉 SUCCESS! Data is being saved correctly.")
    else:
        logger.warning(
            "No comments found. Check if there are new comments on your Facebook page."
        )

except Exception as e:
    logger.error(f"❌ Error: {e}", exc_info=True)
