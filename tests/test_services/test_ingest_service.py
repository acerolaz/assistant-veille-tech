from __future__ import annotations

import pytest

from app.services.ingest_service import persist_websub_push


@pytest.mark.asyncio
async def test_persist_websub_push_no_db_is_noop() -> None:
    """With db=None (no DB_URL), must not raise."""
    articles = [{"url": "https://example.com/a", "title": "T", "source": "S"}]
    await persist_websub_push(articles, "https://example.com/feed", db=None)


@pytest.mark.asyncio
async def test_persist_websub_push_empty_articles_no_db() -> None:
    """Empty article list with db=None must not raise."""
    await persist_websub_push([], "https://example.com/feed", db=None)
