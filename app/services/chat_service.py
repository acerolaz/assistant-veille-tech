from __future__ import annotations

from app.agents.veille_agent import run_agent
from app.schemas import ChatRequest, ChatResponse


async def handle_chat(req: ChatRequest) -> ChatResponse:
    return await run_agent(req.question, req.topics)
