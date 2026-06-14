from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.veille_agent import _extract_tool_outputs, run_agent
from app.schemas import ChatResponse

_FAKE_CHUNK = {
    "id": "doc1",
    "content": "Python async tips",
    "metadata": {
        "title": "Async Python",
        "source": "tech-blog",
        "date": "2024-01-01",
        "url": "https://example.com/async",
        "tags": "python,async",
    },
    "distance": 0.1,
}

_FAKE_ARTICLE = {
    "title": "Fresh Python news",
    "source": "newsapi",
    "date": "2024-01-02",
    "url": "https://news.com/python",
    "content": "Python 3.13 released",
    "tags": ["python"],
}


@pytest.mark.asyncio
async def test_run_agent_returns_degraded_when_llm_not_configured() -> None:
    with (
        patch("app.agents.veille_agent.get_llm", return_value=None),
        patch("app.agents.veille_agent.retrieval.retrieve", return_value=[]),
        patch("app.agents.veille_agent.fresh_news.fetch", new_callable=AsyncMock, return_value=[]),
    ):
        result = await run_agent("python async", [])

    assert isinstance(result, ChatResponse)
    assert result.status == "degraded"
    assert "LLM non configuré" in result.answer


@pytest.mark.asyncio
async def test_run_agent_returns_ok_with_answer_and_cards() -> None:
    action_index = MagicMock()
    action_index.tool = "search_index"
    action_fresh = MagicMock()
    action_fresh.tool = "fetch_fresh_news"

    mock_result = {
        "output": "Voici une synthèse sur Python.",
        "intermediate_steps": [
            (action_index, json.dumps([_FAKE_CHUNK])),
            (action_fresh, json.dumps([_FAKE_ARTICLE])),
        ],
    }

    mock_executor = MagicMock()
    mock_executor.ainvoke = AsyncMock(return_value=mock_result)

    with (
        patch("app.agents.veille_agent.get_llm", return_value=MagicMock()),
        patch("app.agents.veille_agent.create_tool_calling_agent", return_value=MagicMock()),
        patch("app.agents.veille_agent.AgentExecutor", return_value=mock_executor),
    ):
        result = await run_agent("python async", ["python"])

    assert result.status == "ok"
    assert result.answer == "Voici une synthèse sur Python."
    assert len(result.cards) == 2
    assert result.cards[0].title == "Async Python"
    assert result.cards[1].title == "Fresh Python news"


@pytest.mark.asyncio
async def test_run_agent_returns_degraded_on_executor_error() -> None:
    mock_executor = MagicMock()
    mock_executor.ainvoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    with (
        patch("app.agents.veille_agent.get_llm", return_value=MagicMock()),
        patch("app.agents.veille_agent.create_tool_calling_agent", return_value=MagicMock()),
        patch("app.agents.veille_agent.AgentExecutor", return_value=mock_executor),
        patch("app.agents.veille_agent.retrieval.retrieve", return_value=[]),
        patch("app.agents.veille_agent.fresh_news.fetch", new_callable=AsyncMock, return_value=[]),
    ):
        result = await run_agent("python async", [])

    assert result.status == "degraded"
    assert "erreur agent" in result.answer


@pytest.mark.asyncio
async def test_run_agent_appends_topics_to_user_input() -> None:
    """Topics are included in the prompt sent to the executor."""
    captured: list[dict] = []

    async def _capture(payload: dict) -> dict:
        captured.append(payload)
        return {"output": "ok", "intermediate_steps": []}

    mock_executor = MagicMock()
    mock_executor.ainvoke = _capture

    with (
        patch("app.agents.veille_agent.get_llm", return_value=MagicMock()),
        patch("app.agents.veille_agent.create_tool_calling_agent", return_value=MagicMock()),
        patch("app.agents.veille_agent.AgentExecutor", return_value=mock_executor),
    ):
        await run_agent("dernières sorties", ["python", "rust"])

    assert "python" in captured[0]["input"]
    assert "rust" in captured[0]["input"]


def test_extract_tool_outputs_routes_by_tool_name() -> None:
    action_index = MagicMock()
    action_index.tool = "search_index"
    action_fresh = MagicMock()
    action_fresh.tool = "fetch_fresh_news"

    steps = [
        (action_index, json.dumps([_FAKE_CHUNK])),
        (action_fresh, json.dumps([_FAKE_ARTICLE])),
    ]

    retrieved, fresh = _extract_tool_outputs(steps)

    assert retrieved == [_FAKE_CHUNK]
    assert fresh == [_FAKE_ARTICLE]


def test_extract_tool_outputs_ignores_invalid_json() -> None:
    action = MagicMock()
    action.tool = "search_index"

    retrieved, fresh = _extract_tool_outputs([(action, "not-valid-json")])

    assert retrieved == []
    assert fresh == []


def test_extract_tool_outputs_ignores_unknown_tool_names() -> None:
    action = MagicMock()
    action.tool = "unknown_tool"

    retrieved, fresh = _extract_tool_outputs([(action, json.dumps([{"x": 1}]))])

    assert retrieved == []
    assert fresh == []
