from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.ingest_repository import IngestRepository
from app.services.ingest_service import persist_websub_push

TOPIC = "https://example.com/feed"
ARTICLE = {"url": "https://example.com/a", "title": "T", "source": "S"}


@pytest.mark.asyncio
async def test_persist_websub_push_no_db_is_noop() -> None:
    """With db=None (no DB_URL), must not raise."""
    await persist_websub_push([ARTICLE], TOPIC, db=None)


@pytest.mark.asyncio
async def test_persist_websub_push_empty_articles_no_db() -> None:
    """Empty article list with db=None must not raise."""
    await persist_websub_push([], TOPIC, db=None)


def test_delete_stale_websub_articles_for_topic_no_session() -> None:
    """Repository short-circuits and returns [] when session is None."""
    repo = IngestRepository(None)
    result = asyncio.get_event_loop().run_until_complete(
        repo.delete_stale_websub_articles_for_topic(TOPIC)
    )
    assert result == []


@pytest.mark.asyncio
async def test_persist_websub_push_triggers_stale_cleanup_when_articles_present() -> None:
    """Stale cleanup runs (repo + chroma) when fresh articles arrive."""
    stale_url = "https://example.com/old"

    mock_repo = MagicMock()
    mock_repo.create_run = AsyncMock(return_value=None)
    mock_repo.delete_stale_websub_articles_for_topic = AsyncMock(return_value=[stale_url])

    with (
        patch("app.services.ingest_service.IngestRepository", return_value=mock_repo),
        patch("app.services.ingest_service.run_in_threadpool", new_callable=AsyncMock) as mock_tp,
    ):
        await persist_websub_push([ARTICLE], TOPIC, db=None)

    mock_repo.delete_stale_websub_articles_for_topic.assert_awaited_once_with(TOPIC)
    first_call_fn = mock_tp.call_args_list[0].args[0]
    assert first_call_fn.__name__ == "_delete_stale_from_chroma"


@pytest.mark.asyncio
async def test_persist_websub_push_skips_stale_cleanup_when_no_articles() -> None:
    """Stale cleanup is not triggered when the push carries no articles."""
    mock_repo = MagicMock()
    mock_repo.create_run = AsyncMock(return_value=None)
    mock_repo.delete_stale_websub_articles_for_topic = AsyncMock(return_value=[])

    with patch("app.services.ingest_service.IngestRepository", return_value=mock_repo):
        await persist_websub_push([], TOPIC, db=None)

    mock_repo.delete_stale_websub_articles_for_topic.assert_not_awaited()
