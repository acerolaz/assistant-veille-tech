# Assistant Veille Tech — Nauda Palisse

Nauda Palisse — assistant de veille technologique. RAG sur Chroma + injection de news fraîches + scraping de sources tech.

## Fonctionnalités

- Sélection de sujets populaires (Python, JavaScript, AI/ML, DevOps, CSharp) + saisie libre
- Question en langage naturel → réponse synthétique citant ses sources
- **Agent LangChain** (tool-calling) : décide dynamiquement d'interroger l'index interne (`search_index`) et/ou l'actualité fraîche (`fetch_fresh_news`) selon la question
- Retrieval sémantique sur une base vectorielle (ChromaDB) alimentée par scraping et NewsAPI
- Injection d'articles récents au moment du chat : ChromaDB en premier, fallback live NewsAPI si < 3 résultats (cold start)
- Mode dégradé automatique si LLM non configuré (retourne les sources brutes sans synthèse)
- UI Next.js : grille de cards (titre, source, date, snippet, tags couleur, lien)

## Stack

- **Backend** : Python 3.11, uv, FastAPI ≥0.115, Pydantic 2
- **RAG** : ChromaDB 0.5, sentence-transformers 3 (`intfloat/multilingual-e5-small`)
- **Database** : ChromaDB (vectorielle), Postgresql (traces de l'assistant, historique des chats et sources des sujets techniques)
- **Azure services** : Azure AI Inference (Kimi-K2.6)
- **Ingestion** : WebSub / PubSubHubbub (callback FastAPI `/webhook/websub`), NewsAPI, scraping httpx
- **LLM** : LangChain 0.3 + `langchain-azure-ai` → Azure AI Inference (Kimi-K2.6)
- **Scraping / HTTP** : httpx 0.27, BeautifulSoup 4, markdownify
- **Frontend** : Next.js 15 (App Router), React 19, TypeScript 5, Tailwind CSS 4
- **Orchestration** : Docker Compose (chromadb + backend + frontend)

## Layout

```
.
├── app/                        # backend FastAPI
│   ├── main.py                 # app factory, lifespan (WebSub subscribe), middleware
│   ├── config.py               # Settings via pydantic-settings (.env)
│   ├── db.py                   # SQLAlchemy async engine + session factory
│   ├── agents/
│   │   └── veille_agent.py     # LangChain tool-calling agent (search_index + fetch_fresh_news)
│   ├── ingest/
│   │   ├── news_api.py         # NewsApiIngester : fetch NewsAPI → list[dict]
│   │   ├── scraper.py          # Scraper : fetch URL → Markdown via httpx + BS4
│   │   ├── cleaning.py         # HTML→Markdown, dedup, chunking, strip_boilerplate
│   │   ├── enrich.py           # enrich_retrieval() : normalise tags + source_type
│   │   └── fresh_news.py       # FeedXmlParser : parse RSS/Atom XML WebSub pushes
│   ├── migrations/             # Alembic env + versions
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # DB query layer (IngestRepository …)
│   ├── routers/
│   │   ├── chat.py             # POST /chat → handle_chat()
│   │   ├── topics.py           # GET /topics, POST /topics/news
│   │   └── websub.py           # GET+POST /webhook/websub (WebSub hub callback)
│   ├── runtime/
│   │   └── fresh_news.py       # fetch() : ChromaDB 24 h + live NewsAPI fallback
│   ├── schemas/                # Pydantic request/response models
│   ├── services/
│   │   ├── chat_service.py     # handle_chat() → run_agent()
│   │   ├── ingest_service.py   # persist_websub_push() → Postgres + ChromaDB
│   │   ├── llm_service.py      # get_llm(), _build_cards(), compose_answer()
│   │   └── topics_service.py   # handle_fetch_news() → run_agent()
│   └── vector_db/
│       ├── connection.py       # get_client() / get_collection() (ChromaDB HttpClient)
│       └── retrieval.py        # embed(), retrieve(), retrieve_recent()
├── tests/
│   ├── acceptance/             # tests end-to-end (fetch, ingestion, health)
│   ├── test_routers/           # tests HTTP des endpoints (TestClient + mocks)
│   ├── test_services/          # tests unitaires services + agent
│   └── test_vector_db/         # tests unitaires ChromaDB (EphemeralClient)
├── web/                        # frontend Next.js 15
│   ├── app/                    # App Router (page principale + layout)
│   ├── lib/api.ts              # client REST vers le backend
│   └── Dockerfile
├── Dockerfile.backend
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── .env.example
```

## Setup

```bash
cp .env.example .env          # renseigner AZURE_AI_INFERENCE_*, NEWS_API_KEY
make install                  # uv sync (backend)
make up                       # docker compose up -d (chromadb + backend + frontend)
```

- Backend : http://localhost:8000 (`/health`, `/topics`, `/chat`)
- Frontend : http://localhost:3000
- ChromaDB : http://localhost:8002

Tests :

```bash
make test                     # uv run pytest
```

Fichiers de test :
- `tests/acceptance/` — `test_cleaning.py`, `test_fresh_news.py`, `test_news_api_ingester.py`, `test_scraper.py`
- `tests/test_routers/` — `test_agent_endpoints.py`, `test_health.py`
- `tests/test_services/` — `test_veille_agent.py`, `test_fresh_news.py`, `test_enrich.py`, `test_ingest_service.py`
- `tests/test_vector_db/` — `test_chroma.py`

Ingestion (CLI) :

```bash
make ingest                   # passe par scripts/ingest_cli.py
```

## Sources potentielles

Voici quelques pistes de sources publiques utilisables pour alimenter l'index :

- **NewsAPI v2** (`/everything`, `/top-headlines`) — documentation : https://newsapi.org/docs
- **Blogs et agrégateurs techniques** — par exemple Hacker News (front page / item API), DEV.to, Smashing Magazine, lobste.rs
- **Changelogs produits** — par exemple Vercel, OpenAI, GitHub, Anthropic, Stripe
- **Pages de docs / annonces** — par exemple les release notes des frameworks de l'écosystème (Next.js, FastAPI, LangChain), les changelogs Python / Node

Le choix exact des sources reste à arbitrer en fonction des sujets ciblés et de la fraîcheur attendue.

## Flux de données

```
[WebSub push / NewsAPI / Scraper]
           │
           ▼
  [ingest_service.persist_websub_push()]
   HTML → Markdown → dedup → chunk → embed
           │
           ▼
  [ChromaDB  +  PostgreSQL (ingest_runs)]

           ┄┄┄  au moment du chat  ┄┄┄

[POST /chat  ou  POST /topics/news]
           │
           ▼
  [VeilleAgent.run_agent()]   ← LangChain tool-calling (max 4 itérations)
     ├─ tool: search_index(query)
     │       └── retrieval.retrieve() → enrich_retrieval()
     │           (normalise tags, source_type = "internal")
     └─ tool: fetch_fresh_news(query)
             └── fresh_news.fetch()
                 ├── ChromaDB retrieve_recent() (fenêtre 24 h)
                 └── fallback: NewsApiIngester.run() si < 3 résultats
           │
           ▼
  [_build_cards() → ChatResponse(answer, cards, status)]
           │
           ▼
  [UI  — grille de cards]
```

## Aller plus loin (optionnel)

**Postgres** est déjà intégré (`app/db.py`, Alembic) et utilisé pour tracer les souscriptions WebSub (`ingest_runs`). La stack est extensible pour porter des comptes utilisateur (sign-up / sign-in), des sujets favoris et un historique des recherches. Cela ajouterait des endpoints `/users`, `/me/favorites`, `/me/history` et une page « Mon compte » côté frontend, avec un schéma user-scoped et les obligations RGPD associées (hash des mots de passe, durée de conservation, droit à l'effacement).

## Utiles

```bash
make fmt        # ruff format + autofix
make lint       # ruff check
make typecheck  # mypy
make logs       # docker compose logs -f
make down       # stop services
```

## Licence

Interne Nauda Palisse.

## Contact

veille@nauda-palisse.example
