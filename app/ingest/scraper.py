from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.ingest.cleaning import clean_html_to_markdown
from app.schemas import Article

logger = logging.getLogger(__name__)


@dataclass
class Scraper:
    user_agent: str = "nauda-palisse-veille/0.1"
    timeout: float = 10.0

    def run(self, urls: list[str]) -> list[dict[str, Any]]:
        """Scrape URLs and return articles as list of dicts.

        Uses Article (Pydantic) for validation, returns list of dicts.
        """
        if not urls:
            return []

        articles: list[dict[str, Any]] = []

        for idx, url in enumerate(urls):
            try:
                with httpx.Client() as client:
                    response = client.get(
                        url,
                        headers={"User-Agent": self.user_agent},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()

                content = clean_html_to_markdown(response.text)

                soup = BeautifulSoup(response.text, "html.parser")
                title = ""
                title_tag = soup.find("title") or soup.find("h1")
                if title_tag:
                    title = title_tag.get_text(strip=True)

                article = Article(
                    id=f"scraped-{idx}",
                    title=title or "No title",
                    source=url.split("/")[2],
                    date=datetime.now(timezone.utc),
                    url=url,
                    content=content,
                    tags=[],
                )
                articles.append(article.model_dump(mode="json"))
                logger.info(f"Scraped: {url}")

            except Exception as exc:
                logger.error(f"Failed to scrape {url}: {exc}")
                continue

        logger.info(f"Total scraped: {len(articles)} articles from {len(urls)} URLs")
        return articles
