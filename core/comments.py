from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import List, Optional, Set

import requests
from playwright.sync_api import BrowserContext


@dataclass
class Comment:
    id: str
    post_id: str
    author: str
    avatar_url: str | None
    message: str
    created_at: datetime
    permalink: str | None = None
    raw: dict | None = None


class CommentFetcher:
    def __init__(
        self,
        cfg: dict,
        logger,
        context: Optional[BrowserContext] = None,
        processed_ids: Optional[Set[str]] = None,
    ) -> None:
        self.cfg = cfg
        self.demo = cfg.get("demo", False)  # Mặc định là False - dùng data thật
        self._seen: set[str] = set(processed_ids or set())
        self._seen_lock = Lock()  # Thread-safe cho _seen set
        self.logger = logger.getChild("comments")
        self.context = context

    def mark_processed(self, comment_id: str) -> None:
        with self._seen_lock:
            self._seen.add(comment_id)

    def clear_seen_cache(self) -> None:
        """Clear _seen cache để tránh memory leak trong long-running process"""
        with self._seen_lock:
            self._seen.clear()
            self.logger.debug("Cleared seen cache")

    def get_user_comment_history(self, user_id: str, limit: int = 5) -> List[Comment]:
        """Lấy lịch sử comment của user trên page (để hiểu context)"""
        token = self.cfg.get("graph_access_token")

        page_id = self.cfg.get("page_id")
        version = self.cfg.get("graph_version", "v17.0")

        if not token or not page_id:
            return []

        try:
            # Tìm tất cả comments của user trên page
            url = f"https://graph.facebook.com/{version}/{page_id}/feed"
            resp = requests.get(
                url,
                params={
                    "access_token": token,
                    "fields": "comments{from,message,created_time}",
                    "limit": 20,
                },
                timeout=10,
            )
            if not resp.ok:
                return []

            user_comments = []
            posts = resp.json().get("data", [])
            for post in posts:
                comments_data = post.get("comments", {}).get("data", [])
                for c in comments_data:
                    from_info = c.get("from", {})
                    if from_info.get("id") == user_id:
                        user_comments.append(
                            Comment(
                                id=c.get("id", ""),
                                post_id=post.get("id", ""),
                                author=from_info.get("name", "Unknown"),
                                avatar_url=None,
                                message=c.get("message", ""),
                                created_at=self._parse_fb_time(
                                    c.get("created_time", "")
                                ),
                                raw=c,
                            )
                        )
                        if len(user_comments) >= limit:
                            return user_comments
            return user_comments
        except Exception as exc:
            self.logger.warning("Không thể lấy lịch sử comment: %s", exc)
            return []

    def _parse_fb_time(self, value: str) -> datetime:
        try:
            if value.endswith("+0000"):
                value = value[:-5] + "+00:00"
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.utcnow()

    def _fetch_graph_comments(self, limit: int, retry: int = 3) -> List[Comment]:
        # Đọc token trực tiếp từ config (long-lived 60 days)
        token = self.cfg.get("graph_access_token")

        page_id = self.cfg.get("page_id")
        if not token or not page_id:
            return []

        comments: List[Comment] = []
        version = self.cfg.get("graph_version", "v17.0")

        def handle_rate_limit(exc: requests.HTTPError, attempt: int) -> bool:
            """Xử lý rate limit với exponential backoff. Returns True nếu nên retry."""
            if exc.response is None:
                return False
            try:
                error_data = exc.response.json().get("error", {})
                error_code = error_data.get("code")
                error_subcode = error_data.get("error_subcode")

                # Rate limit error codes: 4, 17, 32, 613
                if error_code in {4, 17, 32, 613}:
                    wait_time = min(60 * (2**attempt), 300)  # Max 5 minutes
                    self.logger.warning(
                        "⏱️  Rate limited (code %s), waiting %ds before retry %d/%d",
                        error_code,
                        wait_time,
                        attempt + 1,
                        retry,
                    )
                    time.sleep(wait_time)
                    return True
                # Token expired
                elif error_code == 190:
                    self.logger.error(
                        "❌ Token expired (subcode %s)\n"
                        "   → Vui lòng cập nhật token mới trong .env hoặc config.json",
                        error_subcode,
                    )
                    return False  # Không retry vì token hết hạn
            except Exception:
                pass
            return False

        def fetch_posts(endpoint: str) -> List[dict]:
            url = f"https://graph.facebook.com/{version}/{page_id}/{endpoint}"
            resp = requests.get(url, params={"access_token": token, "limit": 5})
            resp.raise_for_status()
            return resp.json().get("data", [])

        def fetch_comments_for_post(post_id: str) -> List[dict]:
            url = f"https://graph.facebook.com/{version}/{post_id}/comments"
            resp = requests.get(
                url,
                params={
                    "access_token": token,
                    "filter": "stream",
                    "order": "reverse_chronological",
                    "limit": limit,
                    "fields": "from{id,name,picture},message,created_time,permalink_url,id",
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

        try:
            posts = []
            for attempt in range(retry):
                try:
                    posts = fetch_posts("published_posts")
                    break
                except requests.HTTPError as exc:
                    if handle_rate_limit(exc, attempt) and attempt < retry - 1:
                        continue
                    body = exc.response.text if exc.response is not None else ""
                    self.logger.warning(
                        "published_posts failed: %s | body=%s", exc, body
                    )
                    try:
                        posts = fetch_posts("posts")
                        break
                    except requests.HTTPError:
                        if attempt < retry - 1:
                            time.sleep(5)
                        else:
                            raise

            for post in posts:
                post_id = post["id"]
                for attempt in range(retry):
                    try:
                        data = fetch_comments_for_post(post_id)
                        break
                    except requests.HTTPError as exc:
                        if handle_rate_limit(exc, attempt) and attempt < retry - 1:
                            continue
                        body = exc.response.text if exc.response is not None else ""
                        self.logger.warning(
                            "comments fetch failed for %s: %s | body=%s",
                            post_id,
                            exc,
                            body,
                        )
                        if attempt < retry - 1:
                            time.sleep(2)
                        else:
                            data = []
                            break

                for c in data:
                    cid = c.get("id")
                    if not cid:
                        continue

                    # Thread-safe check và add
                    with self._seen_lock:
                        if cid in self._seen:
                            continue
                        self._seen.add(cid)

                    author_info = c.get("from") or {}
                    if author_info.get("id") == page_id:
                        # Skip bot/self comments
                        continue

                    comments.append(
                        Comment(
                            id=cid,
                            post_id=post_id,
                            author=author_info.get("name", "Unknown"),
                            avatar_url=(author_info.get("picture") or {})
                            .get("data", {})
                            .get("url"),
                            message=c.get("message", ""),
                            created_at=self._parse_fb_time(c.get("created_time", "")),
                            permalink=c.get("permalink_url"),
                            raw=c,
                        )
                    )
                    if len(comments) >= limit:
                        return comments
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            self.logger.error("Graph comment fetch failed: %s | body=%s", exc, body)
        except Exception as exc:
            self.logger.error("Graph comment fetch failed: %s", exc)
        return comments

    def _fetch_playwright_comments(self, limit: int) -> List[Comment]:
        if not self.context:
            return []
        comments: List[Comment] = []
        try:
            page_id = self.cfg.get("page_id")
            if not page_id:
                return []
            page = self.context.new_page()
            page.goto(
                f"https://www.facebook.com/{page_id}", wait_until="domcontentloaded"
            )
            page.wait_for_timeout(1500)
            elements = page.query_selector_all("div[aria-label='Comment']")[:limit]
            for el in elements:
                cid = el.get_attribute("data-commentid") or f"pw-{len(comments)+1}"

                # Thread-safe check và add
                with self._seen_lock:
                    if cid in self._seen:
                        continue
                    self._seen.add(cid)

                author = el.get_attribute("data-commenter") or "Unknown"
                message = el.inner_text()
                comments.append(
                    Comment(
                        id=cid,
                        post_id=f"{page_id}-post",
                        author=author,
                        avatar_url=None,
                        message=message,
                        created_at=datetime.utcnow(),
                        permalink=None,
                        raw={"playwright": True},
                    )
                )
                if len(comments) >= limit:
                    break
            page.close()
        except Exception as exc:
            self.logger.warning("Playwright comment fetch failed: %s", exc)
        return comments

    def fetch_new(self, limit: int = 10) -> List[Comment]:
        if self.demo:
            samples = [
                Comment(
                    id="c1",
                    post_id="p1",
                    author="Lan",
                    avatar_url=None,
                    message="Cho minh xin gia",
                    created_at=datetime.utcnow(),
                ),
                Comment(
                    id="c2",
                    post_id="p1",
                    author="Minh",
                    avatar_url=None,
                    message="ib minh nhe",
                    created_at=datetime.utcnow(),
                ),
                Comment(
                    id="c3",
                    post_id="p2",
                    author="UserX",
                    avatar_url=None,
                    message="http://spam.com giam gia cuc soc",
                    created_at=datetime.utcnow(),
                ),
            ]
            new_items = []
            with self._seen_lock:
                new_items = [c for c in samples if c.id not in self._seen][:limit]
                for c in new_items:
                    self._seen.add(c.id)
            return new_items

        comments = self._fetch_graph_comments(limit)
        if comments:
            return comments

        return self._fetch_playwright_comments(limit)
