from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.runtime import fresh_news


@pytest.mark.asyncio
async def test_fetch_returns_list_of_articles() -> None:
    out = await fresh_news.fetch(query="python", since=None)
    assert isinstance(out, list)
    for art in out:
        assert "title" in art
        assert "url" in art
        assert "source" in art
        assert "date" in art


@pytest.mark.asyncio
async def test_fetch_filters_by_since() -> None:
    since = datetime.now(timezone.utc) - timedelta(days=2)
    out = await fresh_news.fetch(query="ai", since=since)
    assert isinstance(out, list)

    for article in out:
        if article.get("date"):
            try:
                article_date = datetime.fromisoformat(article["date"].replace("Z", "+00:00"))
                if article_date.tzinfo is None:
                    article_date = article_date.replace(tzinfo=timezone.utc)
                assert article_date >= since, f"Article date {article_date} is before {since}"
            except (ValueError, AttributeError):
                pass


@pytest.mark.asyncio
async def test_fetch_empty_topics_returns_empty() -> None:
    out = await fresh_news.fetch(query="", since=None)
    assert out == []
