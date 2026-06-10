from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.schemas import Article

logger = logging.getLogger(__name__)


@dataclass
class NewsApiIngester:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    def _fetch_topic(
        self,
        client: httpx.Client,
        topic: str,
        from_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch one page of NewsAPI articles for a single topic and return raw dicts."""
        response = client.get(
            self.settings.news_api_base_url,
            params={
                "q": topic,
                "from": from_date,
                "apiKey": self.settings.news_api_key,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 100,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            logger.error("NewsAPI error for topic '%s': %s", topic, data.get("message"))
            return []
        page = data.get("articles", [])
        logger.info(
            "Fetched %d articles for topic '%s' (%d total available)",
            len(page),
            topic,
            data.get("totalResults", 0),
        )
        return page

    def run(self, topics: list[str]) -> list[dict[str, Any]]:
        """Fetch articles from NewsAPI for the last 7 days, one page per topic.

        Uses Article (Pydantic) for validation, returns list of dicts.
        """
        if not topics:
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        articles: list[dict[str, Any]] = []

        seen_ids: set[str] = set()
        with httpx.Client() as client:
            for topic in topics:
                try:
                    page = self._fetch_topic(client, topic, from_date)
                    for idx, item in enumerate(page):
                        article = Article(
                            id=f"{topic}-{idx}",
                            title=item.get("title", ""),
                            source=item.get("source", {}).get("name", "NewsAPI"),
                            date=item.get("publishedAt"),
                            url=item.get("url", ""),
                            content=item.get("content", ""),
                            tags=[topic],
                        )
                        d = article.model_dump(mode="json")
                        if d["id"] not in seen_ids:
                            seen_ids.add(d["id"])
                            articles.append(d)
                except Exception as exc:
                    logger.error("NewsAPI fetch failed for topic '%s': %s", topic, exc)

        return articles
