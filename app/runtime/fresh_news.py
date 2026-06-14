from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import async_db_session
from app.ingest.news_api import NewsApiIngester
from app.repositories.ingest_repository import IngestRepository
from app.vector_db.retrieval import retrieve_recent

logger = logging.getLogger(__name__)

_MIN_FRESH = 3


async def subscribe_to_feed(feed_url: str) -> None:
    """Subscribe to the WebSub hub for a single RSS feed URL.

    Checks ingest_runs first — skips if an active subscription exists within the
    10-day lease window to avoid redundant re-subscribes.
    """
    settings = get_settings()
    if not settings.websub_callback_url:
        logger.warning("WEBSUB_CALLBACK_URL not set — skipping WebSub subscription")
        return

    callback_url = f"{settings.websub_callback_url}?topic={quote(feed_url, safe='')}"

    async with async_db_session() as session:
        repo = IngestRepository(session)
        try:
            if await repo.has_active_subscription(feed_url):
                logger.info(
                    "Active WebSub subscription found for %s — skipping re-subscribe", feed_url
                )
                return
        except Exception as exc:
            logger.warning(
                "DB dedup check failed for %s (%s) — proceeding with subscription", feed_url, exc
            )
            await session.rollback()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    settings.websub_hub_url,
                    data={
                        "hub.callback": callback_url,
                        "hub.topic": feed_url,
                        "hub.mode": "subscribe",
                        "hub.secret": settings.websub_secret,
                        "hub.lease_seconds": 864000,
                    },
                    timeout=10.0,
                )
            sub_status = "ok" if resp.status_code in (200, 202, 204) else "error"
            logger.info(
                "WebSub subscription %s for %s (HTTP %s)", sub_status, feed_url, resp.status_code
            )
            await repo.record_subscription(feed_url, sub_status)
        except httpx.RequestError as exc:
            logger.error("WebSub subscription failed for %s: %s", feed_url, exc)
            await repo.record_subscription(feed_url, "error", str(exc))


async def fetch(
    query: str,
    since: datetime | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return fresh articles matching the given query.

    Queries ChromaDB first (24 h window by default). Falls back to a live
    NewsAPI call when fewer than _MIN_FRESH results are found, keeping the
    chat path side-effect-free (no ChromaDB write on fallback).
    """
    if not query.strip():
        return []

    chroma = await run_in_threadpool(retrieve_recent, query, limit, since)
    if len(chroma) >= _MIN_FRESH:
        return chroma

    settings = get_settings()
    if not settings.news_api_key:
        logger.info("news_api_key not set — skipping NewsAPI fallback")
        return chroma

    try:
        api_articles: list[dict[str, Any]] = await run_in_threadpool(
            lambda: NewsApiIngester(settings).run([query])
        )
    except Exception as exc:
        logger.warning("NewsAPI fallback failed: %s", exc)
        return chroma

    seen_urls = {a.get("url") for a in chroma}
    merged = list(chroma)
    for art in api_articles:
        if art.get("url") not in seen_urls:
            merged.append(art)
            seen_urls.add(art.get("url"))
    return merged[:limit]
