# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `assistant-veille-tech/`.

```bash
# Setup
cp .env.example .env        # Fill in Azure AI, NewsAPI, and ChromaDB secrets
make install                # uv sync (install Python deps)
make up                     # Start all services (ChromaDB, backend, frontend) via Docker Compose

# Services
# Backend:  http://localhost:8000  (API docs at /docs)
# Frontend: http://localhost:3000
# ChromaDB: http://localhost:8002

# Development
make test                   # Run pytest suite
make fmt                    # ruff format + ruff check --fix
make lint                   # ruff check only
make typecheck              # mypy app
make logs                   # Tail all container logs
make down                   # Stop services

# Ingestion CLI
make ingest                 # Fetch news for default topics
make scrape                 # Scrape a single URL
make chat-test              # curl smoke test against /chat

# Run a single test file
uv run pytest tests/acceptance/test_cleaning.py -v

# Run ingestion manually
PYTHONPATH=. uv run python scripts/ingest_cli.py news --topic python --topic ai-ml
PYTHONPATH=. uv run python scripts/ingest_cli.py scrape --url https://example.com/article
```

## Architecture

This is a **RAG (Retrieval-Augmented Generation) assistant** for technical news watch (veille tech). It surfaces curated articles and answers questions using a vector database + LLM.

### Data Flow

**Ingestion (offline / scheduled):**
```
NewsAPI / Web scraper
  → HTML → Markdown conversion (markdownify + BeautifulSoup)
  → Deduplication + boilerplate removal (app/ingest/cleaning.py)
  → Chunking: 1200 chars, 120 char overlap (langchain-text-splitters)
  → Embedding: intfloat/multilingual-e5-small (sentence-transformers)
  → ChromaDB (stored with metadata: title, source, date, tags, url)
```

**Query (real-time, per user request):**
```
POST /chat  {question, topics}
  → Query expansion: topic slugs appended to question
  → Semantic search in ChromaDB → top-8 chunks  (app/rag/retrieval.py)
  → Post-retrieval enrichment hook               (app/ingest/enrich.py)
  → Live NewsAPI fetch for selected topics        (app/runtime/fresh_news.py)
  → Context assembly (retrieved + fresh news)
  → LangChain → Azure AI Inference (Kimi-K2.6)  (app/rag/llm.py)
  → Response: {answer, cards[], status}
```

### Key Components

**`app/rag/`** — The retrieval + generation pipeline:
- `chroma_client.py` — ChromaDB HTTP client factory (uses `CHROMA_URL`)
- `retrieval.py` — Embeds the query, runs similarity search, returns `Article` objects
- `llm.py` — Builds the LangChain chain, calls Azure AI, returns structured answer; gracefully degrades (returns raw sources) if credentials are absent

**`app/ingest/`** — Document preparation:
- `news_api.py` — Async NewsAPI v2 fetcher, 7-day window, paginated
- `scraper.py` — httpx scraper + HTML→Markdown
- `cleaning.py` — Boilerplate removal, deduplication by URL/ID, chunking
- `enrich.py` — Post-retrieval hook (stub; intended for metadata enrichment)

**`app/runtime/fresh_news.py`** — Live news injection at query time. Currently returns stub data. Contains a WebSub (PubSubHubbub) template with HMAC validation for when upstream contract is finalized — **do not replace this file with a working implementation without confirming the upstream spec.**

**`app/main.py`** — Three routes: `GET /health`, `GET /topics`, `POST /chat`. Chat orchestration is in `app/chat.py`.

**`web/`** — Next.js 15 / React 19 / TypeScript 5 / Tailwind 4 frontend. Topic selector, free-text question input, results grid with article cards. API client in `web/lib/api.ts`.

**`scripts/ingest_cli.py`** — Typer CLI wrapping the ingest pipeline; the primary way to populate ChromaDB.

### Graceful Degradation

The system has three response statuses: `ok` (LLM answered with sources), `empty` (no relevant chunks found), `degraded` (LLM unavailable — returns raw source cards without synthesized answer). Handle all three in the frontend.

### Author-Locked Stubs

Several modules in `app/ingest/` and `app/runtime/` are intentionally left as stubs pending upstream requirements. When working in these files, provide conceptual guidance rather than full implementations unless the upstream contract is confirmed.

### Environment Variables

See `.env.example`. Key variables:
- `AZURE_AI_INFERENCE_ENDPOINT` / `AZURE_AI_INFERENCE_API_KEY` / `AZURE_AI_INFERENCE_MODEL` — LLM
- `CHROMA_URL` — `http://chromadb:8000` in Docker, `http://localhost:8002` locally
- `CHROMA_COLLECTION` — ChromaDB collection name (default: `articles`)
- `EMBEDDING_MODEL` — `intfloat/multilingual-e5-small`
- `NEWS_API_KEY` — NewsAPI v2 key
- `NEXT_PUBLIC_API_URL` — Backend URL as seen from the browser

### Planned but Not Implemented

- PostgreSQL integration (user accounts, session traces, favorites) — Alembic structure exists in `app/migrations/` but is unused
- WebSub real-time feed subscription in `fresh_news.py`
