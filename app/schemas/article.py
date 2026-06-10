from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Article(BaseModel):
    id: str
    title: str
    source: str
    date: datetime | None = None
    content: str
    url: HttpUrl | str
    tags: list[str] = Field(default_factory=list)


class ArticleCard(BaseModel):
    title: str
    source: str
    date: str | None = None
    snippet: str
    url: str
    tags: list[str] = Field(default_factory=list)
