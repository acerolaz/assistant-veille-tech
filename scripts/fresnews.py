"""Génère le token WebSub si absent et déclenche la souscription au feed Medium/csharp.

Lancement :
    uv run python scripts/fresnews.py
"""
import logging
import secrets
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ENV_FILE = Path(".env")


def _ensure_websub_secret() -> None:
    """Write WEBSUB_SECRET to .env once if the field is empty."""
    lines = ENV_FILE.read_text().splitlines(keepends=True) if ENV_FILE.exists() else []
    for i, line in enumerate(lines):
        if line.startswith("WEBSUB_SECRET="):
            if line.strip() == "WEBSUB_SECRET=":
                token = secrets.token_hex(32)
                lines[i] = f"WEBSUB_SECRET={token}\n"
                ENV_FILE.write_text("".join(lines))
                logger.info("WEBSUB_SECRET generated and saved to .env")
            else:
                logger.info("WEBSUB_SECRET already set — skipping")
            return
    # Field not present at all — append it
    token = secrets.token_hex(32)
    with ENV_FILE.open("a") as f:
        f.write(f"\nWEBSUB_SECRET={token}\n")
    logger.info("WEBSUB_SECRET generated and appended to .env")


async def _main() -> None:
    from app.config import get_settings
    get_settings.cache_clear()

    from app.runtime.fresh_news import subscribe_to_feed
    settings = get_settings()
    for feed_url in settings.rss_feed_urls:
        await subscribe_to_feed(feed_url)


if __name__ == "__main__":
    import asyncio

    _ensure_websub_secret()
    asyncio.run(_main())
