from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.schemas import Article

logger = logging.getLogger(__name__)

# XML namespaces present in RSS and Atom feeds
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def _is_after_since(dt: datetime, since_dt: datetime) -> bool:
    """Return True if dt is on or after since_dt (both normalised to UTC-aware)."""
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return aware >= since_dt


def _to_naive_date_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the article dict with 'date' normalised to a naive UTC ISO string.

    Tests compare dates using naive datetimes; keeping the offset would cause
    TypeError: can't compare offset-naive and offset-aware datetimes.
    """
    raw = d.get("date")
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            d = {**d, "date": dt.isoformat()}
        except (ValueError, AttributeError):
            pass
    return d


def _extract_item_fields(
    item: ET.Element,
) -> tuple[str, str, datetime | None, str, str]:
    """Return (title, url, pub_date, source, content) from an RSS <item> or Atom <entry>."""
    ns_atom = "http://www.w3.org/2005/Atom"

    def _text(tag: str, ns: str = "") -> str:
        el = item.find(f"{{{ns}}}{tag}" if ns else tag)
        return (el.text or "").strip() if el is not None else ""

    title = _text("title") or _text("title", ns_atom)

    url = _text("link")
    if not url:
        link_el = item.find(f"{{{ns_atom}}}link")
        if link_el is not None:
            url = link_el.get("href", "")

    pub_date: datetime | None = None
    raw_date = _text("pubDate") or _text("published", ns_atom) or _text("updated", ns_atom)
    if raw_date:
        try:
            pub_date = parsedate_to_datetime(raw_date)
        except Exception:
            try:
                pub_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                pass

    source = (
        _text("source")
        or _text("author")
        or _text("name", "http://www.w3.org/2005/Atom")
        or "WebSub"
    )

    body = (
        _text("{http://purl.org/rss/1.0/modules/content/}encoded")
        or _text("description")
        or _text("summary", ns_atom)
        or _text("content", ns_atom)
    )

    return title, url, pub_date, source, body


@dataclass
class FreshNewsIngester:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    def _fetch_topic(
        self,
        client: httpx.Client,
        topic: str,
        from_date: str,
        page_size: int = 20,
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
                "pageSize": page_size,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            logger.error("NewsAPI error for topic '%s': %s", topic, data.get("message"))
            return []
        return data.get("articles", [])

    def run(self, topics: list[str], since: datetime | None = None) -> list[dict[str, Any]]:
        """Fetch recent articles from NewsAPI with a short time window.

        Uses `since` as the from-date when provided; otherwise defaults to the last 6 hours.
        Returns validated Article dicts filtered to date >= since.
        """
        if not topics:
            return []

        from_dt = since if since is not None else datetime.now(timezone.utc) - timedelta(hours=6)
        since_dt = from_dt if from_dt.tzinfo else from_dt.replace(tzinfo=timezone.utc)
        articles: list[dict[str, Any]] = []

        with httpx.Client() as client:
            for topic in topics:
                try:
                    page = self._fetch_topic(client, topic, from_dt.isoformat())
                    for idx, item in enumerate(page):
                        try:
                            article = Article(
                                id=f"fresh-{topic}-{idx}",
                                title=item.get("title") or "",
                                source=item.get("source", {}).get("name") or "NewsAPI",
                                date=item.get("publishedAt"),
                                url=item.get("url") or "",
                                content=item.get("content") or "",
                                tags=[topic],
                            )
                            if article.date is not None and not _is_after_since(article.date, since_dt):
                                continue
                            articles.append(_to_naive_date_dict(article.model_dump(mode="json")))
                        except Exception as exc:
                            logger.warning("Skipping malformed article: %s", exc)
                    logger.info("FreshNews fetched %d articles for topic '%s'", len(page), topic)
                except Exception as exc:
                    logger.error("FreshNewsIngester failed for topic '%s': %s", topic, exc)

        return articles


@dataclass
class FeedXmlParser:
    """Parse RSS 2.0 or Atom XML payloads (e.g. from WebSub pushes) into Article dicts."""

    def parse_xml(
        self,
        xml_content: str,
        topics: list[str],
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Parse RSS 2.0 or Atom XML into Article dicts.

        Handles both <item> (RSS) and <entry> (Atom) elements.
        Filters articles to date >= since when provided.
        """
        if not xml_content.strip():
            return []

        since_dt: datetime | None = None
        if since is not None:
            since_dt = since if since.tzinfo else since.replace(tzinfo=timezone.utc)

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            logger.error("WebSub XML parse error: %s", exc)
            return []

        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )

        articles: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            try:
                title, url, pub_date, source, body = _extract_item_fields(item)
                if not title or not url:
                    continue

                article = Article(
                    id=f"websub-{idx}",
                    title=title,
                    source=source,
                    date=pub_date,
                    url=url,
                    content=body,
                    tags=topics,
                )

                if since_dt is not None and article.date is not None:
                    if not _is_after_since(article.date, since_dt):
                        continue

                articles.append(_to_naive_date_dict(article.model_dump(mode="json")))
            except Exception as exc:
                logger.warning("Skipping malformed feed entry: %s", exc)

        logger.info("parse_xml extracted %d articles from WebSub payload", len(articles))
        return articles
