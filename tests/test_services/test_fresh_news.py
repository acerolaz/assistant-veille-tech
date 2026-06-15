from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.runtime.fresh_news import fetch, unsubscribe_from_feed

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


_FEED = "https://medium.com/feed/tag/csharp"
_SETTINGS = MagicMock(
    websub_callback_url="http://localhost:8000/webhook/websub",
    websub_hub_url="https://pubsubhubbub.appspot.com/",
)


def _make_http_mock(status_code: int = 202) -> AsyncMock:
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.post = AsyncMock(return_value=MagicMock(status_code=status_code))
    return mock


def _make_db_mock() -> tuple[AsyncMock, AsyncMock]:
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, session


@pytest.mark.asyncio
async def test_unsubscribe_from_feed_posts_unsubscribe_to_hub() -> None:
    mock_http = _make_http_mock()
    mock_repo = MagicMock(invalidate_subscription=AsyncMock())
    mock_cm, _ = _make_db_mock()

    with (
        patch("app.runtime.fresh_news.get_settings", return_value=_SETTINGS),
        patch("app.runtime.fresh_news.httpx.AsyncClient", return_value=mock_http),
        patch("app.runtime.fresh_news.async_db_session", return_value=mock_cm),
        patch("app.runtime.fresh_news.IngestRepository", return_value=mock_repo),
    ):
        await unsubscribe_from_feed(_FEED)

    mock_http.post.assert_awaited_once()
    data = mock_http.post.call_args.kwargs["data"]
    assert data["hub.mode"] == "unsubscribe"
    assert data["hub.topic"] == _FEED


@pytest.mark.asyncio
async def test_unsubscribe_from_feed_calls_invalidate_subscription() -> None:
    mock_http = _make_http_mock()
    mock_repo = MagicMock(invalidate_subscription=AsyncMock())
    mock_cm, _ = _make_db_mock()

    with (
        patch("app.runtime.fresh_news.get_settings", return_value=_SETTINGS),
        patch("app.runtime.fresh_news.httpx.AsyncClient", return_value=mock_http),
        patch("app.runtime.fresh_news.async_db_session", return_value=mock_cm),
        patch("app.runtime.fresh_news.IngestRepository", return_value=mock_repo),
    ):
        await unsubscribe_from_feed(_FEED)

    mock_repo.invalidate_subscription.assert_awaited_once_with(_FEED)


@pytest.mark.asyncio
async def test_unsubscribe_from_feed_skips_when_no_callback_url() -> None:
    with (
        patch(
            "app.runtime.fresh_news.get_settings",
            return_value=MagicMock(websub_callback_url=""),
        ),
        patch("app.runtime.fresh_news.httpx.AsyncClient") as mock_cls,
    ):
        await unsubscribe_from_feed(_FEED)

    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_unsubscribe_from_feed_logs_error_on_request_failure() -> None:
    mock_http = _make_http_mock()
    mock_http.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
    mock_repo = MagicMock(invalidate_subscription=AsyncMock())
    mock_cm, _ = _make_db_mock()

    with (
        patch("app.runtime.fresh_news.get_settings", return_value=_SETTINGS),
        patch("app.runtime.fresh_news.httpx.AsyncClient", return_value=mock_http),
        patch("app.runtime.fresh_news.async_db_session", return_value=mock_cm),
        patch("app.runtime.fresh_news.IngestRepository", return_value=mock_repo),
    ):
        await unsubscribe_from_feed(_FEED)  # must not raise

    mock_repo.invalidate_subscription.assert_not_awaited()
