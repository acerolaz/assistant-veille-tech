from __future__ import annotations

import sys
from pathlib import Path

import chromadb
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
async def async_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def ephemeral_chroma_client() -> chromadb.EphemeralClient:
    """In-memory Chroma client for isolated unit tests."""
    return chromadb.EphemeralClient()
