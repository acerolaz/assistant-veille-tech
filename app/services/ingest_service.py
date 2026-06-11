from __future__ import annotations

import logging
from typing import Any

import chromadb.errors
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.ingest.cleaning import clean_html_to_markdown, dedupe
from app.repositories.ingest_repository import IngestRepository
from app.vector_db.connection import get_collection

logger = logging.getLogger(__name__)


def _delete_stale_from_chroma(urls: list[str]) -> None:
    """Synchronous ChromaDB batch delete — called via run_in_threadpool."""
    collection = get_collection()
    collection.delete(ids=urls)


def _upsert_to_chroma(articles: list[dict[str, Any]], topic: str) -> int:
    """Synchronous ChromaDB upsert — called via run_in_threadpool."""
    collection = get_collection()
    for article in articles:
        collection.upsert(
            ids=[str(article.get("url") or article["id"])],
            documents=[article.get("content") or ""],
            metadatas=[
                {
                    "title": article.get("title") or "",
                    "source": article.get("source") or "",
                    "date": str(article.get("date") or ""),
                    "url": str(article.get("url") or ""),
                    "tags": topic,
                }
            ],
        )
    return len(articles)


async def persist_websub_push(
    articles: list[dict[str, Any]],
    topic: str,
    db: AsyncSession | None,
) -> None:
    """Clean, deduplicate, and persist a WebSub push batch to PostgreSQL and ChromaDB."""
    raw_count = len(articles)

    for article in articles:
        if article.get("content"):
            article["content"] = clean_html_to_markdown(article["content"])

    articles = dedupe(articles)

    repo = IngestRepository(db)

    if articles:
        stale_urls = await repo.delete_stale_websub_articles_for_topic(topic)
        if stale_urls:
            try:
                await run_in_threadpool(_delete_stale_from_chroma, stale_urls)
            except chromadb.errors.ChromaError as exc:
                logger.warning("ChromaDB stale delete failed for topic %s: %s", topic, exc)

    run_id = await repo.create_run("websub_push", [topic])
    if run_id is None:
        return

    try:
        for article in articles:
            await repo.add_article(
                run_id=run_id,
                article_id=str(article.get("url") or ""),
                title=str(article.get("title") or ""),
                publication=str(article.get("source") or ""),
                url=str(article.get("url") or ""),
                topic=topic,
            )

        if raw_count == 0:
            await repo.empty_run(run_id)
            return

        stored = 0
        try:
            stored = await run_in_threadpool(_upsert_to_chroma, articles, topic)
        except chromadb.errors.ChromaError as exc:
            logger.error("ChromaDB upsert failed for topic %s: %s", topic, exc)

        await repo.finish_run(run_id, fetched=raw_count, stored=stored)

    except SQLAlchemyError as exc:
        logger.error("persist_websub_push DB error: %s", exc)
        await repo.fail_run(run_id, str(exc))
