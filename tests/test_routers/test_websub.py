from __future__ import annotations

import hashlib
import hmac
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.main import app

FEED_URL = "https://medium.com/feed/tag/csharp"
SECRET = "test-secret"


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.rss_feed_urls = [FEED_URL]
    s.websub_secret = SECRET
    return s


async def _null_db() -> AsyncGenerator[AsyncSession | None, None]:
    yield None


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def override_db() -> None:
    app.dependency_overrides[get_db] = _null_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def wsclient() -> TestClient:
    return TestClient(app)


def test_receive_feed_update_returns_202(wsclient: TestClient) -> None:
    body = b"<feed></feed>"
    with patch("app.routers.websub.get_settings", return_value=_mock_settings()):
        resp = wsclient.post(
            f"/webhook/websub?topic={FEED_URL}",
            content=body,
            headers={"X-Hub-Signature": _sign(body, SECRET), "Content-Type": "application/xml"},
        )
    assert resp.status_code == 202


def test_receive_feed_update_bad_signature_returns_403(wsclient: TestClient) -> None:
    with patch("app.routers.websub.get_settings", return_value=_mock_settings()):
        resp = wsclient.post(
            f"/webhook/websub?topic={FEED_URL}",
            content=b"<feed></feed>",
            headers={"X-Hub-Signature": "sha256=deadbeef"},
        )
    assert resp.status_code == 403


def test_receive_feed_update_unknown_topic_returns_400(wsclient: TestClient) -> None:
    with patch("app.routers.websub.get_settings", return_value=_mock_settings()):
        resp = wsclient.post(
            "/webhook/websub?topic=https://unknown.example.com/feed",
            content=b"<feed></feed>",
            headers={"X-Hub-Signature": "sha256=abc"},
        )
    assert resp.status_code == 400


def test_receive_feed_update_missing_signature_returns_401(wsclient: TestClient) -> None:
    with patch("app.routers.websub.get_settings", return_value=_mock_settings()):
        resp = wsclient.post(
            f"/webhook/websub?topic={FEED_URL}",
            content=b"<feed></feed>",
        )
    assert resp.status_code == 401


def test_delete_websub_returns_204_and_calls_unsubscribe_for_each_feed(
    wsclient: TestClient,
) -> None:
    with (
        patch("app.routers.websub.get_settings", return_value=_mock_settings()),
        patch(
            "app.routers.websub.unsubscribe_from_feed",
            new_callable=AsyncMock,
        ) as mock_unsub,
    ):
        resp = wsclient.delete("/webhook/websub")

    assert resp.status_code == 204
    mock_unsub.assert_awaited_once_with(FEED_URL)


def test_delete_websub_calls_unsubscribe_for_every_configured_feed(
    wsclient: TestClient,
) -> None:
    second_url = "https://example.com/feed/python"
    settings = _mock_settings()
    settings.rss_feed_urls = [FEED_URL, second_url]

    with (
        patch("app.routers.websub.get_settings", return_value=settings),
        patch(
            "app.routers.websub.unsubscribe_from_feed",
            new_callable=AsyncMock,
        ) as mock_unsub,
    ):
        resp = wsclient.delete("/webhook/websub")

    assert resp.status_code == 204
    assert mock_unsub.await_count == 2
    mock_unsub.assert_any_await(FEED_URL)
    mock_unsub.assert_any_await(second_url)
