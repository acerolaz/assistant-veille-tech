from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingester: Mapped[str] = mapped_column(String(20), nullable=False)
    topics: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="running", nullable=False)
    fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    articles: Mapped[list[IngestArticle]] = relationship(
        "IngestArticle", back_populates="run", cascade="all, delete-orphan"
    )


class IngestArticle(Base):
    __tablename__ = "ingest_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingest_runs.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publication: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    run: Mapped[IngestRun] = relationship("IngestRun", back_populates="articles")
