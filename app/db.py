from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# ── Async engine (FastAPI / repositories) ────────────────────────────────────

_async_engine = None
_AsyncSessionLocal = None


def _async_url(url: str) -> str:
    if not os.path.exists("/.dockerenv"):
        url = url.replace("@postgres:", "@localhost:")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def get_async_engine():
    global _async_engine, _AsyncSessionLocal
    db_url = get_settings().db_url
    if not db_url:
        return None
    if _async_engine is None:
        _async_engine = create_async_engine(_async_url(db_url), pool_pre_ping=True)
        _AsyncSessionLocal = async_sessionmaker(_async_engine, expire_on_commit=False)
    return _async_engine


@asynccontextmanager
async def async_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Async session for FastAPI routes and services."""
    if get_async_engine() is None or _AsyncSessionLocal is None:
        yield None
        return
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Sync engine (CLI scripts) ────────────────────────────────────────────────

_sync_engine: Engine | None = None


def _sync_url(url: str) -> str:
    if not os.path.exists("/.dockerenv"):
        url = url.replace("@postgres:", "@localhost:")
    return url


def get_engine() -> Engine | None:
    global _sync_engine
    db_url = get_settings().db_url
    if not db_url:
        return None
    if _sync_engine is None:
        _sync_engine = create_engine(_sync_url(db_url), pool_pre_ping=True)
    return _sync_engine


@contextmanager
def db_session() -> Generator[Session | None, None, None]:
    """Sync session for CLI scripts."""
    engine = get_engine()
    if engine is None:
        yield None
        return
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute(session: Session, sql: str, **params: object) -> object:
    """Run textual SQL and return the first row (or None). Used by CLI scripts."""
    from sqlalchemy.exc import ResourceClosedError

    result = session.execute(text(sql), params)
    try:
        return result.fetchone()
    except ResourceClosedError:
        return None
