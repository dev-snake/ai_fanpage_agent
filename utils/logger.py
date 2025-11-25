import logging
from typing import Optional


def setup_logger(level: str = "INFO") -> logging.Logger:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("fanpage_agent")


def get_child(name: str, parent: Optional[logging.Logger] = None) -> logging.Logger:
    base = parent or logging.getLogger("fanpage_agent")
    return base.getChild(name)
