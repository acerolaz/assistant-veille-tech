from __future__ import annotations

from typing import Any


def enrich_retrieval(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrichit les chunks récupérés par la recherche de similarité.

    Par exemple, on peut faire appel à des APIs externes pour ajouter des
    métadonnées, ou reformuler le contenu des chunks.

    Ici, on se contente d'ajouter une métadonnée "enriched" à True pour
    illustrer le concept.
    """
    enriched = []
    for chunk in retrieved:
        meta = chunk.get("metadata", {})
        meta["enriched"] = True
        enriched.append({**chunk, "metadata": meta})
    return enriched
