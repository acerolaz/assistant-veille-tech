from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.runtime.fresh_news import fetch

_CHROMA_ARTICLE = {
    "title": "ChromaDB hit",
    "source": "interne",
    "date": "2024-01-01",
    "url": "https://chroma.example.com/1",
    "content": "content",
    "tags": ["python"],
}

_API_ARTICLE = {
    "id": "api-1",
    "title": "NewsAPI hit",
    "source": "newsapi",
    "date": "2024-01-02",
    "url": "https://newsapi.example.com/1",
    "content": "fresh content",
    "tags": ["python"],
}


@pytest.mark.asyncio
async def test_fetch_returns_chroma_results_when_enough() -> None:
    three_hits = [_CHROMA_ARTICLE] * 3
    with (
        patch("app.runtime.fresh_news.retrieve_recent", return_value=three_hits),
        patch("app.runtime.fresh_news.NewsApiIngester") as mock_ingester_cls,
    ):
        result = await fetch("python")

    assert result == three_hits
    mock_ingester_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_falls_back_to_newsapi_when_chroma_cold() -> None:
    mock_ingester = MagicMock()
    mock_ingester.run.return_value = [_API_ARTICLE]

    with (
        patch("app.runtime.fresh_news.retrieve_recent", return_value=[]),
        patch("app.runtime.fresh_news.NewsApiIngester", return_value=mock_ingester),
        patch(
            "app.runtime.fresh_news.get_settings",
            return_value=MagicMock(news_api_key="key123"),
        ),
    ):
        result = await fetch("python")

    assert len(result) == 1
    assert result[0]["title"] == "NewsAPI hit"
    mock_ingester.run.assert_called_once_with(["python"])


@pytest.mark.asyncio
async def test_fetch_returns_empty_when_no_key_and_chroma_cold() -> None:
    with (
        patch("app.runtime.fresh_news.retrieve_recent", return_value=[]),
        patch(
            "app.runtime.fresh_news.get_settings",
            return_value=MagicMock(news_api_key=""),
        ),
        patch("app.runtime.fresh_news.NewsApiIngester") as mock_ingester_cls,
    ):
        result = await fetch("python")

    assert result == []
    mock_ingester_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_deduplicates_by_url() -> None:
    duplicate = {**_API_ARTICLE, "url": _CHROMA_ARTICLE["url"]}
    new_api = {**_API_ARTICLE, "url": "https://newsapi.example.com/new"}
    mock_ingester = MagicMock()
    mock_ingester.run.return_value = [duplicate, new_api]

    with (
        patch("app.runtime.fresh_news.retrieve_recent", return_value=[_CHROMA_ARTICLE]),
        patch("app.runtime.fresh_news.NewsApiIngester", return_value=mock_ingester),
        patch(
            "app.runtime.fresh_news.get_settings",
            return_value=MagicMock(news_api_key="key123"),
        ),
    ):
        result = await fetch("python")

    urls = [a["url"] for a in result]
    assert len(urls) == len(set(urls))
    assert len(result) == 2


@pytest.mark.asyncio
async def test_fetch_returns_empty_on_blank_query() -> None:
    with (
        patch("app.runtime.fresh_news.retrieve_recent") as mock_retrieve,
        patch("app.runtime.fresh_news.NewsApiIngester") as mock_ingester_cls,
    ):
        result = await fetch("   ")

    assert result == []
    mock_retrieve.assert_not_called()
    mock_ingester_cls.assert_not_called()
