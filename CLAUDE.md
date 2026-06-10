# FastAPI + ChromaDB Project

## Commands

`uvicorn app.main:app --reload` — Start development server on port 8000

`pytest` — Run test suite

`pytest --cov=app` — Run tests with coverage report

`alembic upgrade head` — Apply database migrations

`alembic revision --autogenerate -m "description"` — Create new migration

`ruff check .` — Run linter (checks PEP 8 and import sorting)

`ruff format .` — Format code (ensures PEP 8 compliance)

`mypy app/` — Type check

## Architecture

* **Framework**: FastAPI with async/await throughout
* **Database**: SQLAlchemy 2.0 async with PostgreSQL
* **Vector DB**: ChromaDB for embeddings and vector similarity search
* **Migrations**: Alembic for schema migrations
* **Validation**: Pydantic v2 models for request/response schemas
* **Auth**: JWT tokens via python-jose, password hashing with passlib
* **Testing**: pytest with httpx AsyncClient for API tests and ephemeral Chroma clients

## Project Structure

```
app/
├── main.py              # FastAPI app factory, middleware, startup/shutdown
├── config.py            # Settings via pydantic-settings (reads .env)
├── dependencies.py      # Shared FastAPI dependencies (get_db, get_current_user, get_chroma_client)
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response models
├── routers/             # API route modules (one per domain)
├── services/            # Business logic layer (called by routers)
├── repositories/        # Database query layer (called by services)
├── vector_db/           # ChromaDB connection, collections, and vector operations
└── tests/
    ├── conftest.py      # Fixtures: async client, test DB, auth headers, ephemeral Chroma
    ├── test_routers/    # API integration tests
    ├── test_services/   # Unit tests for business logic
    └── test_vector_db/  # Unit/integration tests for vector search

```

## Code Conventions, Style, & SOLID Principles

* **Code Style & Formatting**:
* All Python code must strictly adhere to **PEP 8 conventions**.
* PEP 8 compliance is automatically enforced via `ruff check .` (linter) and `ruff format .` (formatter).
* Proper type hinting (PEP 484) is required on all functions, verified via `mypy`.


* **Single Responsibility Principle (SRP)**:
* Router functions are kept strictly thin; they only delegate requests and return responses.
* The `services/` layer handles core application logic, completely decoupled from HTTP concerns.
* The `repositories/` layer handles relational database queries, while the `vector_db/` layer focuses strictly on ChromaDB operations and embeddings.


* **Open/Closed Principle (OCP)**:
* Code is open for extension but closed for modification.
* Isolate models using separate Create, Update, and Response Pydantic schemas (e.g., `UserCreate`, `UserUpdate`, `UserResponse`) to extend inputs/outputs safely without rewriting core models.
* Introduce new vector similarity metrics or embedding strategies by extending the `vector_db/` layer without altering existing service logic.


* **Liskov Substitution Principle (LSP)**:
* Derived classes or sub-modules must be substitutable for their base abstractions (e.g., implementing Abstract Base Classes/Interfaces for vector repositories).
* All routes return typed Pydantic response models—never return raw dicts or ORM objects—ensuring uniform contract adherence.


* **Interface Segregation Principle (ISP)**:
* Clients are not forced to depend on methods they do not use.
* Utilize FastAPI's dependency injection system to inject precise dependencies (e.g., `db: AsyncSession = Depends(get_db)`, `chroma_client = Depends(get_chroma_client)`) rather than passing monolithic state objects.


* **Dependency Inversion Principle (DIP)**:
* High-level modules (e.g., Services) rely on abstractions (injected dependencies/interfaces) rather than importing hardcoded, concrete database or vector connections.


* **General conventions**:
* Vector operations in ChromaDB should be wrapped in async utility functions or executed using `run_in_threadpool` if utilizing the synchronous Chroma SDK to avoid blocking the event loop.
* Background tasks handled via FastAPI's `BackgroundTasks`, not Celery (unless explicitly needed).



## Error Handling

* Validation errors return 422 with Pydantic's default error format.
* Business logic errors raise `HTTPException` with appropriate status codes.
* Use custom exception handlers in `main.py` for domain-specific error types.
* Never catch broad `Exception` — catch specific exception types.

## Database & Vector Patterns

* Always use `select()` style queries (SQLAlchemy 2.0), not legacy `query()`.
* Relationships use `selectinload()` or `joinedload()` to avoid N+1 queries.
* Transactions are per-request — the dependency handles commit/rollback.
* Use `Annotated` types for common column patterns (e.g., `created_at`, `updated_at`).
* Initialize persistent or ephemeral ChromaDB clients in `vector_db/connection.py` and manage collection retrievals cleanly via repository/service layers.

## Testing (Unit & Acceptance)

* Tests use a separate test database (configured in `conftest.py`).
* Each test runs in a transaction that rolls back — tests don't affect each other.
* Mock external services (email, payment) but hit the real test database.

### Acceptance Tests (Integration)

* Acceptance tests validate the end-to-end flow from the HTTP request down to the database/vector store.
* Use `httpx.AsyncClient` with `app=app` to fire requests against endpoints.

```python
# tests/test_routers/test_search.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_vector_search_endpoint(client: AsyncClient, admin_token_headers):
    # Given an authenticated client and a query payload
    payload = {"query": "agentic workflow", "limit": 3}
    
    # When hitting the search router
    response = await client.post("/api/v1/search/vector", json=payload, headers=admin_token_headers)
    
    # Then acceptance criteria is met (HTTP 200 and structured list response)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)

```

### Unit Tests

* Unit tests isolate specific classes or functions (e.g., Services or Vector Repositories).
* For vector operations, initialize an ephemeral in-memory Chroma client (`chromadb.EphemeralClient()`) within `conftest.py` fixtures to keep unit tests fast, independent, and stateless.

```python
# tests/test_vector_db/test_chroma.py
import pytest
import chromadb
from app.vector_db.repository import ChromaVectorRepository

@pytest.fixture
def ephemeral_chroma_client():
    # Ephemeral memory client for pure unit testing isolated from disk/network
    return chromadb.EphemeralClient()

def test_add_and_query_vectors(ephemeral_chroma_client):
    # Given a clean unit repo instance bound to our ephemeral client
    repo = ChromaVectorRepository(client=ephemeral_chroma_client)
    collection = repo.get_or_create_collection("test-collection")
    
    # When a vector is added
    collection.add(
        documents=["This is a test document about RAG."],
        metadatas=[{"source": "unit-test"}],
        ids=["doc1"]
    )
    
    # Then it can be queried directly in memory
    results = collection.query(query_texts=["RAG"], n_results=1)
    
    assert results["ids"][0][0] == "doc1"

```

## Things to Avoid

* Do NOT use synchronous database drivers or blocking I/O in async routes.
* Do NOT return SQLAlchemy models directly from routes — always use Pydantic schemas.
* Do NOT put business logic in router functions — use the service layer.
* Do NOT use synchronous ChromaDB operations directly in async endpoints without `run_in_threadpool`.
* Do NOT use `*` imports.
* Do NOT hardcode configuration — use pydantic-settings and environment variables.
* Do NOT use global mutable state — use FastAPI's dependency injection system.
