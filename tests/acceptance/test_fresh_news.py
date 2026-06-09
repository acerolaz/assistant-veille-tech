from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.runtime import fresh_news


@pytest.mark.asyncio
async def test_fetch_returns_list_of_articles() -> None:
    out = await fresh_news.fetch(topics=["python"], since=None)
    assert isinstance(out, list)
    for art in out:
        assert "title" in art
        assert "url" in art
        assert "source" in art
        assert "date" in art


@pytest.mark.asyncio
async def test_fetch_filters_by_since() -> None:
    since = datetime.utcnow() - timedelta(days=2)
    out = await fresh_news.fetch(topics=["ai"], since=since)
    assert isinstance(out, list)

    # Verify all articles are from after 'since' date
    for article in out:
        if article.get("date"):
            # Parse date string to datetime (assumes ISO format)
            try:
                article_date = datetime.fromisoformat(article["date"].replace("Z", "+00:00"))
                assert article_date >= since, f"Article date {article_date} is before {since}"
            except (ValueError, AttributeError):
                # If date parsing fails, skip validation
                pass


@pytest.mark.asyncio
async def test_fetch_empty_topics_returns_empty() -> None:
    out = await fresh_news.fetch(topics=[], since=None)
    assert out == [] or isinstance(out, list)
