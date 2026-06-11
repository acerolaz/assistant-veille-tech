from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import chromadb.errors
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.vector_db.connection import get_collection

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed(text: str) -> list[float]:
    embedder = get_embedder()
    vec = embedder.encode([text], normalize_embeddings=True)
    return vec[0].tolist()


def retrieve(query: str, k: int = 8) -> list[dict[str, Any]]:
    try:
        collection = get_collection()
        query_vec = embed(query)
        result = collection.query(query_embeddings=[query_vec], n_results=k)
    except Exception as exc:
        logger.warning("retrieval failed: %s", exc)
        return []

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    return [
        {"id": doc_id, "content": doc, "metadata": meta or {}, "distance": dist}
        for doc_id, doc, meta, dist in zip(ids, docs, metas, distances, strict=False)
    ]


def retrieve_recent(
    query: str,
    k: int = 20,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    threshold = since if since is not None else datetime.now(timezone.utc) - timedelta(hours=24)
    threshold_str = threshold.replace(tzinfo=None).isoformat()
    try:
        collection = get_collection()
        query_vec = embed(query)
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=k,
            where={"date": {"$gte": threshold_str}},
        )
    except (chromadb.errors.ChromaError, ValueError) as exc:
        logger.warning("retrieve_recent failed: %s", exc)
        return []

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]

    return [
        {
            "title": meta.get("title", ""),
            "source": meta.get("source", ""),
            "date": meta.get("date", ""),
            "url": meta.get("url", ""),
            "content": doc,
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        }
        for doc, meta in zip(docs, metas, strict=False)
        if meta is not None
    ]
