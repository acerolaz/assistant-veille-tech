from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat import handle_chat
from app.config import get_settings
from app.runtime.fresh_news import router as websub_router
from app.runtime.fresh_news import subscribe_to_feed
from app.schemas import ChatRequest, ChatResponse, Topic

POPULAR_TOPICS: list[Topic] = [
    Topic(slug="python", label="Python"),
    Topic(slug="javascript", label="JavaScript"),
    Topic(slug="ai-ml", label="AI/ML"),
    Topic(slug="devops", label="DevOps"),
    Topic(slug="web", label="Web"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    for feed_url in get_settings().rss_feed_urls:
        subscribe_to_feed(feed_url)
    yield


app = FastAPI(
    title="Nauda Palisse — Veille Tech",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(websub_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/topics", response_model=list[Topic])
def topics() -> list[Topic]:
    return POPULAR_TOPICS


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    return await handle_chat(req)
