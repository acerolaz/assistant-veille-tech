from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, health, topics
from app.routers import websub as websub_router
from app.runtime.fresh_news import subscribe_to_feed


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    for feed_url in get_settings().rss_feed_urls:
        await subscribe_to_feed(feed_url)
    yield


app = FastAPI(
    title="Nauda Palisse — Veille Tech",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(topics.router)
app.include_router(chat.router)
app.include_router(websub_router.router)
