from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.config import get_settings
from app.db import db_session, execute
from app.ingest.fresh_news import FreshNewsIngester

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook")


def subscribe_to_feed(feed_url: str) -> None:
    """Subscribe to the WebSub hub for a single RSS feed URL.

    Checks ingest_runs first — skips if an active subscription exists within the
    10-day lease window (hub.lease_seconds=864000) to avoid redundant re-subscribes.
    Records the outcome (ok/error) as a 'websub_sub' row in ingest_runs.
    The callback URL includes a ?topic= query parameter so the hub can route
    push notifications back to the correct feed handler.
    """
    settings = get_settings()
    if not settings.websub_callback_url:
        logger.warning("WEBSUB_CALLBACK_URL not set — skipping WebSub subscription")
        return

    callback_url = f"{settings.websub_callback_url}?topic={quote(feed_url, safe='')}"

    with db_session() as session:
        if session is not None:
            try:
                row = execute(
                    session,
                    "SELECT id FROM ingest_runs"
                    " WHERE ingester = 'websub_sub' AND status = 'ok'"
                    " AND topics = :feed_url"
                    " AND started_at > NOW() - INTERVAL '10 days'"
                    " LIMIT 1",
                    feed_url=feed_url,
                )
                if row:
                    logger.info("Active WebSub subscription found for %s — skipping re-subscribe", feed_url)
                    return
            except Exception as exc:
                logger.warning("DB dedup check failed for %s (%s) — proceeding with subscription", feed_url, exc)

        try:
            resp = httpx.post(
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
            if session is not None:
                execute(
                    session,
                    "INSERT INTO ingest_runs (ingester, topics, status, finished_at)"
                    " VALUES ('websub_sub', :topic, :status, NOW())",
                    topic=feed_url,
                    status=sub_status,
                )
        except Exception as exc:
            logger.error("WebSub subscription failed for %s: %s", feed_url, exc)
            if session is not None:
                execute(
                    session,
                    "INSERT INTO ingest_runs"
                    " (ingester, topics, status, error, finished_at)"
                    " VALUES ('websub_sub', :topic, 'error', :error, NOW())",
                    topic=feed_url,
                    error=str(exc),
                )


@router.get("/websub")
async def verify_intent(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_topic: str = Query(..., alias="hub.topic"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_lease_seconds: int | None = Query(None, alias="hub.lease_seconds"),
    topic: str = Query(...),
) -> Response:
    """Step 2 & 3 — echo back hub.challenge to confirm subscription intent."""
    settings = get_settings()
    if hub_mode in ("subscribe", "unsubscribe") and hub_topic == topic and hub_topic in settings.rss_feed_urls:
        logger.info("WebSub handshake verified for topic: %s", hub_topic)
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Topic mismatch or invalid mode.")


@router.post("/websub")
async def receive_feed_update(
    request: Request,
    topic: str = Query(...),
) -> Response:
    """Step 4 & 5 — Content Delivery Phase.

    Called by the hub via HTTP POST whenever a new RSS entry is published.
    Validates the hub's HMAC signature, then passes the XML payload to
    FreshNewsIngester.parse_xml() for structured extraction.
    The ?topic= query param identifies which feed sent the push.
    """
    settings = get_settings()

    if topic not in settings.rss_feed_urls:
        raise HTTPException(status_code=400, detail="Unknown feed topic.")

    # Validate hub signature
    signature = request.headers.get("X-Hub-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature header.")

    raw_body = await request.body()

    sha_type, hub_sign = signature.split("=", 1)
    if sha_type == "sha256":
        local_sign = hmac.new(
            settings.websub_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(local_sign, hub_sign):
            raise HTTPException(status_code=403, detail="Invalid signature.")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported signature type: {sha_type}")

    # Parse XML and extract articles via the ingester, tagging with the feed URL
    xml_content = raw_body.decode("utf-8")
    articles = FreshNewsIngester().parse_xml(xml_content, topics=[topic], since=None)
    logger.info("WebSub push from %s: %d articles extracted", topic, len(articles))

    # Fast return so the hub doesn't time out
    return Response(status_code=202)


async def fetch(
    topics: list[str],
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return fresh articles for the given topics via FreshNewsIngester."""
    return FreshNewsIngester().run(topics, since)
