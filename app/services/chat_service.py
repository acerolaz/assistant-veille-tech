from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_db_session
from app.ingest import enrich as ingest_enrich
from app.repositories.ingest_repository import IngestRepository
from app.runtime import fresh_news
from app.schemas import ChatRequest, ChatResponse
from app.services.llm_service import compose_answer
from app.vector_db import retrieval

logger = logging.getLogger(__name__)


async def handle_chat(req: ChatRequest) -> ChatResponse:
    query = _expand_query(req.question, req.topics)

    retrieved = retrieval.retrieve(query, k=8)

    enriched = ingest_enrich.enrich_retrieval(retrieved)
    if enriched:
        retrieved = enriched

    fresh = await _fetch_fresh_with_trace(req.topics)

    return await compose_answer(
        question=req.question,
        topics=req.topics,
        retrieved_chunks=retrieved,
        fresh_articles=fresh,
    )


async def _fetch_fresh_with_trace(topics: list[str]) -> list[dict[str, Any]]:
    """Call fresh_news.fetch() and record the run in ingest_runs/ingest_articles."""
    async with async_db_session() as session:
        repo = IngestRepository(session)
        run_id = await repo.create_run("fresh_news", topics)

        try:
            articles = await fresh_news.fetch(topics=topics, since=None)
            fetched = len(articles)

            for article in articles:
                await repo.add_article(
                    run_id=run_id,
                    article_id=str(article.get("url") or ""),
                    title=str(article.get("title") or ""),
                    publication=str(article.get("source") or ""),
                    url=str(article.get("url") or ""),
                    topic=", ".join(topics),
                )

            if fetched == 0:
                await repo.empty_run(run_id)
            else:
                await repo.finish_run(run_id, fetched=fetched, stored=0)

            return articles

        except Exception as exc:
            logger.warning("fresh_news fetch failed: %s", exc)
            await repo.fail_run(run_id, str(exc))
            return []


def _expand_query(question: str, topics: list[str]) -> str:
    if not topics:
        return question
    return f"{question} | {', '.join(topics)}"
