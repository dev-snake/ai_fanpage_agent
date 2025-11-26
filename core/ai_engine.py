from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .comments import Comment


class Intent(str, Enum):
    ASK_PRICE = "ask_price"
    INTEREST = "interest"
    SPAM = "spam"
    ABUSE = "abuse"
    MISSING_PHONE = "missing_phone"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    REPLY = "reply"
    HIDE = "hide"
    OPEN_INBOX = "open_inbox"
    IGNORE = "ignore"
    POST = "post"


@dataclass
class Decision:
    intent: Intent
    actions: List[ActionType]
    reply_text: Optional[str]
    confidence: float
    rationale: str = ""


KEYWORDS: Dict[Intent, List[str]] = {
    Intent.ASK_PRICE: ["bao nhiêu", "giá", "gia", "bn", "nhiu"],
    Intent.INTEREST: ["quan tâm", "tư vấn", "mua", "đặt", "đăt", "shop đâu"],
    Intent.SPAM: ["http://", "https://", "cho vay", "săn sale"],
    Intent.ABUSE: ["lừa", "scam", "đm", "dkm", "cc", "địt"],
    Intent.MISSING_PHONE: ["ib", "inbox", "sdt", "sđt", "phone", "call"],
}


def _resolve_openai_key(settings: dict, logger: logging.Logger) -> Optional[str]:
    """Resolve OpenAI API key, skipping obvious placeholders."""
    key = (settings.get("openai_api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        logger.warning("OPENAI_API_KEY missing; fallback to heuristic intent.")
        return None
    if key.startswith("${") or "OPENAI_API_KEY" in key or key.startswith("{"):
        logger.warning("OPENAI_API_KEY looks like a placeholder; update .env/config.")
        return None
    os.environ.setdefault("OPENAI_API_KEY", key)
    return key


def heuristic_classify(message: str) -> Tuple[Intent, float, str]:
    text = message.lower()
    for intent, words in KEYWORDS.items():
        if any(w in text for w in words):
            return intent, 0.78, f"match {intent.value}"
    if len(text) <= 2:
        return Intent.SPAM, 0.6, "very short"
    return Intent.UNKNOWN, 0.4, "fallback"


def generate_reply(intent: Intent, comment: Comment) -> Optional[str]:
    name = comment.author or "bạn"
    if intent == Intent.ASK_PRICE:
        return (
            f"Chào {name}, giá sản phẩm đang ưu đãi. "
            "Bạn cho mình xin số điện thoại hoặc để lại tin nhắn để tư vấn nhanh nhé!"
        )
    if intent == Intent.INTEREST:
        return (
            f"Cảm ơn {name} đã quan tâm! "
            "Bạn để lại SĐT/inbox để mình hỗ trợ chọn mẫu và báo giá chi tiết."
        )
    if intent == Intent.MISSING_PHONE:
        return "Mình đã mở inbox cho bạn, vui lòng check tin nhắn để được hỗ trợ nhanh."
    if intent == Intent.SPAM:
        return None
    if intent == Intent.ABUSE:
        return None
    return (
        "Cảm ơn bạn đã để lại bình luận! Bạn cần thêm thông tin nào cứ nhắn mình nhé."
    )


def llm_classify(
    message: str, settings: dict, logger: logging.Logger
) -> Optional[Tuple[Intent, float, str]]:
    if settings.get("llm_provider") != "openai":
        return None
    try:
        from openai import AuthenticationError, OpenAI, OpenAIError
    except ImportError:
        logger.warning("openai package missing, fallback to rules.")
        return None

    api_key = _resolve_openai_key(settings, logger)
    if not api_key:
        return None

    try:
        client = OpenAI(
            api_key=api_key,
            default_headers={"Authorization": f"Bearer {api_key}"},
        )
    except OpenAIError as exc:  # pragma: no cover
        logger.error("LLM client init failed: %s", exc)
        return None

    prompt = (
        "Bạn là bộ phận phân loại intent cho bình luận Facebook bán hàng. "
        "Intent hợp lệ: ask_price, interest, spam, abuse, missing_phone. "
        "Trả về JSON: {intent, confidence, reason}."
    )
    try:
        res = client.chat.completions.create(
            model=settings.get("openai_model", "gpt-4o-mini"),
            temperature=0.1,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
            extra_headers={"Authorization": f"Bearer {api_key}"},
        )
        content = res.choices[0].message.content or ""
        match_intent = re.search(r"intent\s*[:=]\s*(\w+)", content)
        match_conf = re.search(r"confidence\s*[:=]\s*([0-9.]+)", content)
        intent = Intent(match_intent.group(1)) if match_intent else Intent.UNKNOWN
        confidence = float(match_conf.group(1)) if match_conf else 0.55
        return intent, confidence, "llm"
    except AuthenticationError as exc:  # pragma: no cover
        logger.error(
            "LLM classify failed: authentication error, check OPENAI_API_KEY. %s", exc
        )
        return None
    except Exception as exc:  # pragma: no cover
        logger.error("LLM classify failed: %s", exc)
        return None


def classify_comment(
    comment: Comment, settings: dict, logger: logging.Logger
) -> Decision:
    llm_result = llm_classify(comment.message, settings, logger)
    if llm_result:
        intent, confidence, rationale = llm_result
    else:
        intent, confidence, rationale = heuristic_classify(comment.message)

    actions = [ActionType.REPLY]
    if intent in {Intent.SPAM, Intent.ABUSE}:
        actions = [ActionType.HIDE]
    elif intent == Intent.MISSING_PHONE:
        actions = [ActionType.OPEN_INBOX, ActionType.REPLY]
    elif intent == Intent.UNKNOWN:
        actions = [ActionType.REPLY]

    reply_text = generate_reply(intent, comment)
    return Decision(
        intent=intent,
        actions=actions,
        reply_text=reply_text,
        confidence=confidence,
        rationale=rationale,
    )
