from __future__ import annotations

import json
import logging

from app.db import db_session, execute
from app.ingest import enrich as ingest_enrich
from app.rag import retrieval
from app.rag.llm import compose_answer
from app.runtime import fresh_news
from app.schemas import ChatRequest, ChatResponse

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


async def _fetch_fresh_with_trace(topics: list[str]) -> list[dict]:
    """Call fresh_news.fetch() and record the run in ingest_runs/ingest_articles."""
    with db_session() as session:
        run_id: int | None = None
        if session is not None:
            row = execute(
                session,
                "INSERT INTO ingest_runs (ingester, topics, status)"
                " VALUES (:ingester, :topics, 'running') RETURNING id",
                ingester="fresh_news",
                topics=json.dumps(topics),
            )
            run_id = row[0] if row else None

        try:
            articles = await fresh_news.fetch(topics=topics, since=None)
            fetched = len(articles)

            if session is not None and run_id is not None:
                for article in articles:
                    execute(
                        session,
                        "INSERT INTO ingest_articles"
                        " (run_id, article_id, title, publication, url, topic)"
                        " VALUES (:run_id, :article_id, :title, :publication, :url, :topic)",
                        run_id=run_id,
                        article_id=str(article.get("url") or ""),
                        title=str(article.get("title") or ""),
                        publication=str(article.get("source") or ""),
                        url=str(article.get("url") or ""),
                        topic=", ".join(topics),
                    )
                status = "empty" if fetched == 0 else "ok"
                execute(
                    session,
                    "UPDATE ingest_runs"
                    " SET finished_at=NOW(), status=:status, fetched=:fetched, stored=0"
                    " WHERE id=:run_id",
                    run_id=run_id,
                    status=status,
                    fetched=fetched,
                )
            return articles

        except Exception as exc:
            logger.warning("fresh_news fetch failed: %s", exc)
            if session is not None and run_id is not None:
                execute(
                    session,
                    "UPDATE ingest_runs"
                    " SET finished_at=NOW(), status='error', error=:error"
                    " WHERE id=:run_id",
                    run_id=run_id,
                    error=str(exc),
                )
            return []


def _expand_query(question: str, topics: list[str]) -> str:
    if not topics:
        return question
    return f"{question} | {', '.join(topics)}"
