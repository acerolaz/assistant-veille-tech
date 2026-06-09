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

    def run(self, topics: list[str]) -> list[dict[str, Any]]:
        """Fetch articles from NewsAPI with pagination per topic.

        For each topic, fetches one page (max 100 articles) from the last 7 days in a single request.
        Uses Article (Pydantic) for validation, returns list of dicts.
        """
        if not topics:
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        articles: list[dict[str, Any]] = []

        try:
            with httpx.Client() as client:
                for topic in topics:
                    response = client.get(
                        self.settings.news_api_base_url,
                        params={
                            "q": topic,
                            "from": from_date,
                            "apiKey": self.settings.news_api_key,
                            "sortBy": "publishedAt",
                            "language": "en",
                            "pageSize": 100,  # Max 100 per page (NewsAPI limit)
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") != "ok":
                        logger.error(f"NewsAPI error for topic '{topic}': {data.get('message')}")
                        continue

                    page_articles = data.get("articles", [])

                    for idx, article_data in enumerate(page_articles):
                        article = Article(
                            id=f"{topic}-{idx}",
                            title=article_data.get("title", ""),
                            source=article_data.get("source", {}).get("name", "NewsAPI"),
                            date=article_data.get("publishedAt"),
                            url=article_data.get("url", ""),
                            content=article_data.get("content", ""),
                            tags=[topic],
                        )
                        articles.append(article.model_dump(mode="json"))

                    logger.info(f"Fetched {len(page_articles)} articles for topic '{topic}' ({data.get('totalResults', 0)} total available)")

        except Exception as exc:
            logger.error(f"NewsAPI fetch failed: {exc}")
        return articles
