from __future__ import annotations

import json
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from app.ingest import enrich as ingest_enrich
from app.runtime import fresh_news
from app.schemas import ChatResponse
from app.services.llm_service import _build_cards, get_llm
from app.vector_db import retrieval

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Tu es l'assistant de veille technologique de Nauda Palisse.\n"
    "Utilise search_index pour interroger la base de connaissances interne "
    "et fetch_fresh_news pour les actualités récentes.\n"
    "Réponds en français, de façon factuelle et concise, en citant tes sources."
)


@tool
def search_index(query: str) -> str:
    """Search the internal ChromaDB knowledge base for relevant article chunks."""
    chunks = retrieval.retrieve(query, k=8)
    return json.dumps(ingest_enrich.enrich_retrieval(chunks), ensure_ascii=False, default=str)


@tool
async def fetch_fresh_news(query: str) -> str:
    """Fetch recent articles from the news API for the given free-text query."""
    articles = await fresh_news.fetch(query=query, since=None)
    return json.dumps(articles, ensure_ascii=False, default=str)


_TOOLS = [search_index, fetch_fresh_news]


def _extract_tool_outputs(
    steps: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    retrieved: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    for action, output in steps:
        try:
            data: list[dict[str, Any]] = json.loads(output)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if action.tool == "search_index":
            retrieved.extend(data)
        elif action.tool == "fetch_fresh_news":
            fresh.extend(data)
    return retrieved, fresh


async def run_agent(question: str, topics: list[str]) -> ChatResponse:
    llm = get_llm()

    if llm is None:
        retrieved = retrieval.retrieve(question, k=8)
        fresh = await fresh_news.fetch(query=question, since=None)
        cards = _build_cards(retrieved, fresh)
        return ChatResponse(
            answer=f"{len(cards)} article(s) trouvé(s). LLM non configuré.",
            cards=cards,
            status="degraded",
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    executor = AgentExecutor(
        agent=create_tool_calling_agent(llm, _TOOLS, prompt),
        tools=_TOOLS,
        max_iterations=4,
        verbose=False,
    )

    user_input = question
    if topics:
        user_input = f"{question} (sujets : {', '.join(topics)})"

    try:
        result = await executor.ainvoke({"input": user_input})
    except Exception as exc:
        logger.warning("agent failed: %s", exc)
        retrieved = retrieval.retrieve(question, k=5)
        fresh = await fresh_news.fetch(query=question, since=None, limit=5)
        return ChatResponse(
            answer="Synthèse indisponible (erreur agent).",
            cards=_build_cards(retrieved, fresh),
            status="degraded",
        )

    answer = str(result.get("output", ""))
    retrieved_chunks, fresh_articles = _extract_tool_outputs(
        result.get("intermediate_steps", [])
    )
    return ChatResponse(
        answer=answer,
        cards=_build_cards(retrieved_chunks, fresh_articles),
        status="ok",
    )
