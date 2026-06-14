from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.article import ArticleCard


class FreshNewsRequest(BaseModel):
    query: str
    since: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)


class FreshNewsResponse(BaseModel):
    articles: list[ArticleCard]
