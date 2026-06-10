from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IngestRepository:
    """Encapsulates all SQL for ingest_runs and ingest_articles tables."""

    def __init__(self, session: AsyncSession | None) -> None:
        self._session = session

    async def create_run(self, ingester: str, topics: list[str]) -> int | None:
        if self._session is None:
            return None
        row = await self._session.execute(
            text(
                "INSERT INTO ingest_runs (ingester, topics, status)"
                " VALUES (:ingester, :topics, 'running') RETURNING id"
            ),
            {"ingester": ingester, "topics": json.dumps(topics)},
        )
        result = row.fetchone()
        return result[0] if result else None

    async def finish_run(self, run_id: int, fetched: int, stored: int) -> None:
        if self._session is None or run_id is None:
            return
        await self._session.execute(
            text(
                "UPDATE ingest_runs"
                " SET finished_at=NOW(), status='ok', fetched=:fetched, stored=:stored"
                " WHERE id=:run_id"
            ),
            {"run_id": run_id, "fetched": fetched, "stored": stored},
        )

    async def empty_run(self, run_id: int) -> None:
        if self._session is None or run_id is None:
            return
        await self._session.execute(
            text(
                "UPDATE ingest_runs"
                " SET finished_at=NOW(), status='empty', fetched=0, stored=0"
                " WHERE id=:run_id"
            ),
            {"run_id": run_id},
        )

    async def fail_run(self, run_id: int, error: str) -> None:
        if self._session is None or run_id is None:
            return
        await self._session.execute(
            text(
                "UPDATE ingest_runs"
                " SET finished_at=NOW(), status='error', error=:error"
                " WHERE id=:run_id"
            ),
            {"run_id": run_id, "error": error},
        )

    async def add_article(
        self,
        run_id: int,
        article_id: str,
        title: str,
        publication: str,
        url: str,
        topic: str,
    ) -> None:
        if self._session is None or run_id is None:
            return
        await self._session.execute(
            text(
                "INSERT INTO ingest_articles"
                " (run_id, article_id, title, publication, url, topic)"
                " VALUES (:run_id, :article_id, :title, :publication, :url, :topic)"
            ),
            {
                "run_id": run_id,
                "article_id": article_id,
                "title": title,
                "publication": publication,
                "url": url,
                "topic": topic,
            },
        )

    async def has_active_subscription(self, feed_url: str) -> bool:
        if self._session is None:
            return False
        row = await self._session.execute(
            text(
                "SELECT id FROM ingest_runs"
                " WHERE ingester = 'websub_sub' AND status = 'ok'"
                " AND topics = :feed_url"
                " AND started_at > NOW() - INTERVAL '10 days'"
                " LIMIT 1"
            ),
            {"feed_url": feed_url},
        )
        return row.fetchone() is not None

    async def record_subscription(
        self, feed_url: str, status: str, error: str | None = None
    ) -> None:
        if self._session is None:
            return
        await self._session.execute(
            text(
                "INSERT INTO ingest_runs (ingester, topics, status, finished_at)"
                " VALUES ('websub_sub', :topic, :status, NOW())"
            ),
            {"topic": feed_url, "status": status},
        )
        if error:
            await self._session.execute(
                text(
                    "UPDATE ingest_runs SET error=:error"
                    " WHERE ingester='websub_sub' AND topics=:topic"
                    " ORDER BY id DESC LIMIT 1"
                ),
                {"error": error, "topic": feed_url},
            )
