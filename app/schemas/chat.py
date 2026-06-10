from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.article import ArticleCard


class ChatRequest(BaseModel):
    question: str
    topics: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    cards: list[ArticleCard]
    status: Literal["ok", "empty", "degraded"] = "ok"
