from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine | None:
    """Return a SQLAlchemy engine, or None if DB_URL is not configured."""
    global _engine
    db_url = get_settings().db_url
    if not db_url:
        return None
    if _engine is None:
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


@contextmanager
def db_session() -> Generator[Session | None, None, None]:
    """Yield a SQLAlchemy session, or None when DB_URL is unset (tracing disabled)."""
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
    """Run a textual SQL statement and return the first row (or None).
    
    For SELECT or INSERT...RETURNING queries, returns the first row.
    For UPDATE/INSERT/DELETE queries, returns None.
    """
    from sqlalchemy.exc import ResourceClosedError
    
    result = session.execute(text(sql), params)
    try:
        # Try to fetch a row - works for SELECT and INSERT...RETURNING
        return result.fetchone()
    except ResourceClosedError:
        # Statement doesn't return rows (UPDATE, INSERT, DELETE without RETURNING)
        return None
