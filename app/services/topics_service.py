from __future__ import annotations

from app.agents.veille_agent import run_agent
from app.schemas import ChatResponse
from app.schemas.fresh_news import FreshNewsRequest


async def handle_fetch_news(req: FreshNewsRequest) -> ChatResponse:
    return await run_agent(req.query, [])
