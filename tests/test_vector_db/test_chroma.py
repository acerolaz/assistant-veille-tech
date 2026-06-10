from __future__ import annotations

import chromadb
import pytest


def test_add_and_query_vectors(ephemeral_chroma_client: chromadb.EphemeralClient) -> None:
    collection = ephemeral_chroma_client.get_or_create_collection("test-collection")

    collection.add(
        documents=["This is a test document about RAG."],
        metadatas=[{"source": "unit-test"}],
        ids=["doc1"],
    )

    results = collection.query(query_texts=["RAG"], n_results=1)
    assert results["ids"][0][0] == "doc1"
