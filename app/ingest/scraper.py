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

    def _fetch(self, client: httpx.Client, url: str) -> httpx.Response:
        response = client.get(
            url, headers={"User-Agent": self.user_agent}, timeout=self.timeout
        )
        response.raise_for_status()
        return response

    def _extract_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("title") or soup.find("h1")
        return tag.get_text(strip=True) if tag else "No title"

    def _build_article(self, url: str, html: str, idx: int) -> dict[str, Any]:
        return Article(
            id=f"scraped-{idx}",
            title=self._extract_title(html),
            source=url.split("/")[2],
            date=datetime.now(timezone.utc),
            url=url,
            content=clean_html_to_markdown(html),
            tags=[],
        ).model_dump(mode="json")

    def run(self, urls: list[str]) -> list[dict[str, Any]]:
        """Scrape URLs and return articles as list of dicts."""
        if not urls:
            return []
        articles: list[dict[str, Any]] = []
        with httpx.Client() as client:
            for idx, url in enumerate(urls):
                try:
                    response = self._fetch(client, url)
                    articles.append(self._build_article(url, response.text, idx))
                    logger.info(f"Scraped: {url}")
                except Exception as exc:
                    logger.error(f"Failed to scrape {url}: {exc}")
        logger.info(f"Total scraped: {len(articles)} articles from {len(urls)} URLs")
        return articles
