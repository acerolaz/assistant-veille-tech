from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import async_db_session
from app.repositories.ingest_repository import IngestRepository
from app.vector_db.retrieval import retrieve_recent

logger = logging.getLogger(__name__)


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
    topics: list[str],
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return fresh articles from ChromaDB for the given topics."""
    if not topics:
        return []
    query = ", ".join(topics)
    return await run_in_threadpool(retrieve_recent, query, 20, since)
