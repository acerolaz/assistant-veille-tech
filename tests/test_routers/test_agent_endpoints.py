from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ChatResponse
from app.schemas.article import ArticleCard

_CARD = ArticleCard(
    title="Python 3.13",
    source="blog",
    date="2024-01-01",
    snippet="New features.",
    url="https://example.com",
    tags=["python"],
)
_OK_RESPONSE = ChatResponse(answer="Voici la synthèse.", cards=[_CARD], status="ok")
_DEGRADED_RESPONSE = ChatResponse(
    answer="1 article(s) trouvé(s). LLM non configuré.",
    cards=[_CARD],
    status="degraded",
)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# --- POST /topics/news ---


def test_post_topics_news_returns_200_and_chat_response_shape(client: TestClient) -> None:
    with patch(
        "app.services.topics_service.run_agent",
        new_callable=AsyncMock,
        return_value=_OK_RESPONSE,
    ):
        resp = client.post("/topics/news", json={"query": "intelligence artificielle"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Voici la synthèse."
    assert isinstance(data["cards"], list)
    assert len(data["cards"]) == 1
    assert data["status"] == "ok"


def test_post_topics_news_propagates_degraded_status(client: TestClient) -> None:
    with patch(
        "app.services.topics_service.run_agent",
        new_callable=AsyncMock,
        return_value=_DEGRADED_RESPONSE,
    ):
        resp = client.post("/topics/news", json={"query": "rust"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


def test_post_topics_news_missing_query_returns_422(client: TestClient) -> None:
    resp = client.post("/topics/news", json={})
    assert resp.status_code == 422


def test_post_topics_news_passes_query_to_run_agent(client: TestClient) -> None:
    """The router passes the request query to run_agent unchanged."""
    mock_agent = AsyncMock(return_value=_OK_RESPONSE)
    with patch("app.services.topics_service.run_agent", mock_agent):
        client.post("/topics/news", json={"query": "devops kubernetes"})

    mock_agent.assert_awaited_once_with("devops kubernetes", [])


# --- POST /chat ---


def test_post_chat_returns_200_and_chat_response_shape(client: TestClient) -> None:
    with patch(
        "app.services.chat_service.run_agent",
        new_callable=AsyncMock,
        return_value=_OK_RESPONSE,
    ):
        resp = client.post("/chat", json={"question": "Quelles sont les nouveautés Python ?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Voici la synthèse."
    assert isinstance(data["cards"], list)
    assert data["status"] == "ok"


def test_post_chat_missing_question_returns_422(client: TestClient) -> None:
    resp = client.post("/chat", json={})
    assert resp.status_code == 422


def test_post_chat_passes_question_and_topics_to_run_agent(client: TestClient) -> None:
    """The chat router forwards both question and topics to run_agent."""
    mock_agent = AsyncMock(return_value=_OK_RESPONSE)
    with patch("app.services.chat_service.run_agent", mock_agent):
        client.post("/chat", json={"question": "Explique l'agentic AI", "topics": ["ai", "llm"]})

    mock_agent.assert_awaited_once_with("Explique l'agentic AI", ["ai", "llm"])
