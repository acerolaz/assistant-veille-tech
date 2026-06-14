from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ChatResponse, Topic
from app.schemas.fresh_news import FreshNewsRequest
from app.services.topics_service import handle_fetch_news

router = APIRouter()

POPULAR_TOPICS: list[Topic] = [
    Topic(slug="python", label="Python"),
    Topic(slug="javascript", label="JavaScript"),
    Topic(slug="ai-ml", label="AI/ML"),
    Topic(slug="devops", label="DevOps"),
    Topic(slug="csharp", label="CSharp"),
]


@router.get("/topics", response_model=list[Topic])
def topics() -> list[Topic]:
    return POPULAR_TOPICS


@router.post("/topics/news", response_model=ChatResponse)
async def fetch_news(req: FreshNewsRequest) -> ChatResponse:
    return await handle_fetch_news(req)
