from __future__ import annotations

from typing import AsyncGenerator

import chromadb
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_db_session
from app.vector_db.connection import get_client


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async SQLAlchemy session, or None when DB_URL is unset."""
    async with async_db_session() as session:
        yield session


async def get_chroma_client() -> chromadb.HttpClient:
    """Return the shared ChromaDB HTTP client."""
    return get_client()
