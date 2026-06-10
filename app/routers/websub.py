from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.config import get_settings
from app.ingest.fresh_news import FeedXmlParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook")


@router.get("/websub")
async def verify_intent(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_topic: str = Query(..., alias="hub.topic"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_lease_seconds: int | None = Query(None, alias="hub.lease_seconds"),
    topic: str = Query(...),
) -> Response:
    """Echo back hub.challenge to confirm subscription intent."""
    settings = get_settings()
    if (
        hub_mode in ("subscribe", "unsubscribe")
        and hub_topic == topic
        and hub_topic in settings.rss_feed_urls
    ):
        logger.info("WebSub handshake verified for topic: %s", hub_topic)
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Topic mismatch or invalid mode.")


@router.post("/websub")
async def receive_feed_update(
    request: Request,
    topic: str = Query(...),
) -> Response:
    """Validate HMAC signature and extract articles from WebSub XML payload."""
    settings = get_settings()

    if topic not in settings.rss_feed_urls:
        raise HTTPException(status_code=400, detail="Unknown feed topic.")

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

    xml_content = raw_body.decode("utf-8")
    articles = FeedXmlParser().parse_xml(xml_content, topics=[topic], since=None)
    logger.info("WebSub push from %s: %d articles extracted", topic, len(articles))

    return Response(status_code=202)
