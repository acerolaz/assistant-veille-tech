from __future__ import annotations

from typing import Any


def enrich_retrieval(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise chunk metadata before the agent serialises it to the LLM.

    Ensures tags are always a list, fills missing title/url keys, and stamps
    source_type so the LLM can distinguish internal-index hits from fresh news.
    """
    enriched = []
    for chunk in retrieved:
        meta = dict(chunk.get("metadata") or {})
        raw_tags = meta.get("tags", "")
        if isinstance(raw_tags, str):
            meta["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
        meta.setdefault("title", "")
        meta.setdefault("url", "")
        meta["source_type"] = "internal"
        enriched.append({**chunk, "metadata": meta})
    return enriched
