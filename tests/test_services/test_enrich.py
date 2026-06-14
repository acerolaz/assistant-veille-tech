from __future__ import annotations

from app.ingest.enrich import enrich_retrieval

_CHUNK = {
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


def test_enrich_parses_tags_string_to_list() -> None:
    result = enrich_retrieval([_CHUNK])
    assert result[0]["metadata"]["tags"] == ["python", "async"]


def test_enrich_keeps_tags_list_unchanged() -> None:
    chunk = {**_CHUNK, "metadata": {**_CHUNK["metadata"], "tags": ["ai", "llm"]}}
    result = enrich_retrieval([chunk])
    assert result[0]["metadata"]["tags"] == ["ai", "llm"]


def test_enrich_adds_source_type_internal() -> None:
    result = enrich_retrieval([_CHUNK])
    assert result[0]["metadata"]["source_type"] == "internal"


def test_enrich_fills_missing_title_and_url() -> None:
    chunk = {"id": "x", "content": "text", "metadata": {}, "distance": 0.0}
    result = enrich_retrieval([chunk])
    meta = result[0]["metadata"]
    assert meta["title"] == ""
    assert meta["url"] == ""


def test_enrich_returns_same_count() -> None:
    chunks = [_CHUNK, {**_CHUNK, "id": "doc2"}]
    assert len(enrich_retrieval(chunks)) == 2
