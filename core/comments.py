from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
        self.demo = cfg.get("demo", True)
        self._seen: set[str] = set(processed_ids or set())
        self.logger = logger.getChild("comments")
        self.context = context

    def mark_processed(self, comment_id: str) -> None:
        self._seen.add(comment_id)

    def _parse_fb_time(self, value: str) -> datetime:
        try:
            if value.endswith("+0000"):
                value = value[:-5] + "+00:00"
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.utcnow()

    def _fetch_graph_comments(self, limit: int) -> List[Comment]:
        token = self.cfg.get("graph_access_token")
        page_id = self.cfg.get("page_id")
        if not token or not page_id:
            return []

        comments: List[Comment] = []
        version = self.cfg.get("graph_version", "v17.0")

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
            try:
                posts = fetch_posts("published_posts")
            except requests.HTTPError as exc:
                body = exc.response.text if exc.response is not None else ""
                self.logger.warning("published_posts failed: %s | body=%s", exc, body)
                posts = fetch_posts("posts")

            for post in posts:
                post_id = post["id"]
                try:
                    data = fetch_comments_for_post(post_id)
                except requests.HTTPError as exc:
                    body = exc.response.text if exc.response is not None else ""
                    self.logger.warning(
                        "comments fetch failed for %s: %s | body=%s", post_id, exc, body
                    )
                    continue

                for c in data:
                    cid = c.get("id")
                    if not cid or cid in self._seen:
                        continue

                    author_info = c.get("from") or {}
                    if author_info.get("id") == page_id:
                        # Skip bot/self comments
                        self._seen.add(cid)
                        continue

                    self._seen.add(cid)
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
            page.goto(f"https://www.facebook.com/{page_id}", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            elements = page.query_selector_all("div[aria-label='Comment']")[:limit]
            for el in elements:
                cid = el.get_attribute("data-commentid") or f"pw-{len(comments)+1}"
                if cid in self._seen:
                    continue
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
                self._seen.add(cid)
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
            new_items = [c for c in samples if c.id not in self._seen][:limit]
            for c in new_items:
                self._seen.add(c.id)
            return new_items

        comments = self._fetch_graph_comments(limit)
        if comments:
            return comments

        return self._fetch_playwright_comments(limit)
